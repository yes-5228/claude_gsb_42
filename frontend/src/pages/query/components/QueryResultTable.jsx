import DataTable from '../../../components/common/DataTable.jsx'
import Tag from '../../../components/common/Tag.jsx'
import { DATA_SOURCE_TONE, EXCEEDANCE_STATUS_TONE } from '../../../constants/index.js'
import { formatDateTime, formatNumber } from '../../../utils/format.js'

export default function QueryResultTable({ rows, loading }) {
  const columns = [
    { key: 'measured_at', title: '监测时间', className: 'cell-nowrap', render: (row) => formatDateTime(row.measured_at) },
    { key: 'station', title: '监测点', render: (row) => `${row.station?.code || ''} ${row.station?.name || ''}` },
    { key: 'station_area', title: '区域', render: (row) => row.station?.area || '-' },
    { key: 'pollutant_label', title: '因子', className: 'cell-nowrap' },
    { key: 'period_label', title: '周期', className: 'cell-nowrap' },
    {
      key: 'value',
      title: '监测值',
      align: 'right',
      render: (row) => (
        <span className={row.is_exceeded && row.is_valid ? 'danger-text strong' : ''}>
          {formatNumber(row.value)} <span className="muted small">{row.unit}</span>
        </span>
      )
    },
    { key: 'limit_value', title: '限值', align: 'right', render: (row) => (row.limit_value === null ? '无限值' : formatNumber(row.limit_value)) },
    {
      key: 'is_valid',
      title: '有效性',
      render: (row) =>
        row.is_valid ? <Tag tone="success">有效</Tag> : <Tag tone="danger">校准期·无效</Tag>
    },
    {
      key: 'is_exceeded',
      title: '超标',
      render: (row) =>
        !row.is_valid ? (
          <Tag tone="neutral">不参与</Tag>
        ) : row.is_exceeded ? (
          <Tag tone="danger">是</Tag>
        ) : (
          <Tag tone="success">否</Tag>
        )
    },
    {
      key: 'exceedance_status',
      title: '标注状态',
      render: (row) =>
        row.exceedance_status ? (
          <Tag tone={EXCEEDANCE_STATUS_TONE[row.exceedance_status]}>
            {row.exceedance_status === 'pending' ? '待标注' : row.exceedance_status === 'confirmed' ? '已确认' : '已忽略'}
          </Tag>
        ) : (
          <span className="muted">-</span>
        )
    },
    {
      key: 'data_source_label',
      title: '来源',
      render: (row) => <Tag tone={DATA_SOURCE_TONE[row.data_source]}>{row.data_source_label}</Tag>
    },
    { key: 'device_code', title: '设备', className: 'small mono', render: (row) => row.device_code || '-' },
    { key: 'recorder', title: '录入人', render: (row) => row.recorder || '-' }
  ]

  return (
    <DataTable
      columns={columns}
      rows={rows}
      loading={loading}
      rowClassName={(row) => (row.is_valid ? '' : 'row-invalid')}
      emptyText="没有符合条件的数据, 请调整筛选条件"
      emptyIcon="🔍"
    />
  )
}
