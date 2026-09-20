import DataTable from '../../../components/common/DataTable.jsx'
import Tag from '../../../components/common/Tag.jsx'
import { DATA_SOURCE_TONE } from '../../../constants/index.js'
import { formatDateTime, formatNumber, formatRatio } from '../../../utils/format.js'

export default function MeasurementTable({ rows, loading, onDelete }) {
  const columns = [
    {
      key: 'measured_at',
      title: '监测时间',
      className: 'cell-nowrap',
      render: (row) => formatDateTime(row.measured_at)
    },
    {
      key: 'station',
      title: '监测点',
      render: (row) => (
        <div>
          <div>{row.station?.name || '-'}</div>
          <div className="small muted mono">{row.station?.code || ''}</div>
        </div>
      )
    },
    { key: 'pollutant_label', title: '监测因子', className: 'cell-nowrap' },
    { key: 'period_label', title: '周期', className: 'cell-nowrap' },
    {
      key: 'value',
      title: '监测值',
      align: 'right',
      className: 'cell-nowrap',
      render: (row) => (
        <span className={row.is_exceeded && row.is_valid ? 'danger-text strong' : ''}>
          {formatNumber(row.value)} <span className="muted small">{row.unit}</span>
        </span>
      )
    },
    {
      key: 'limit_value',
      title: '限值',
      align: 'right',
      render: (row) => (row.limit_value === null ? <span className="muted small">无限值</span> : formatNumber(row.limit_value))
    },
    {
      key: 'is_valid',
      title: '有效性',
      render: (row) =>
        row.is_valid ? (
          <Tag tone="success">有效</Tag>
        ) : (
          <Tag tone="danger" title="设备校准期间录入, 保留但不参与达标率统计">
            校准期·无效
          </Tag>
        )
    },
    {
      key: 'is_exceeded',
      title: '超标判定',
      render: (row) =>
        !row.is_valid ? (
          <Tag tone="neutral">不参与</Tag>
        ) : row.is_exceeded ? (
          <Tag tone="danger">{formatRatio(row.exceed_ratio)}</Tag>
        ) : (
          <Tag tone="success">达标</Tag>
        )
    },
    {
      key: 'data_source_label',
      title: '来源',
      render: (row) => <Tag tone={DATA_SOURCE_TONE[row.data_source]}>{row.data_source_label}</Tag>
    },
    {
      key: 'device',
      title: '设备',
      className: 'small muted',
      render: (row) => row.device_code || <span className="muted">-</span>
    },
    { key: 'recorder', title: '录入人', render: (row) => row.recorder || '-' },
    {
      key: 'actions',
      title: '操作',
      align: 'right',
      render: (row) => (
        <button type="button" className="btn btn-sm btn-danger" onClick={() => onDelete(row)}>
          删除
        </button>
      )
    }
  ]

  return (
    <DataTable
      columns={columns}
      rows={rows}
      loading={loading}
      rowClassName={(row) => (row.is_valid ? '' : 'row-invalid')}
      emptyText="暂无监测数据, 请先在上方录入"
      emptyIcon="✍️"
    />
  )
}
