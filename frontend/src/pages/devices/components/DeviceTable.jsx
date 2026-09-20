import DataTable from '../../../components/common/DataTable.jsx'
import Tag from '../../../components/common/Tag.jsx'
import { DEVICE_STATUS_TONE } from '../../../constants/index.js'
import { formatDate, formatDateTime } from '../../../utils/format.js'

export default function DeviceTable({ rows, loading, onDetail, onEdit, onCalibrate, onDelete }) {
  const columns = [
    {
      key: 'code',
      title: '设备编码',
      className: 'cell-nowrap mono',
      render: (row) => (
        <button type="button" className="link-btn" onClick={() => onDetail(row)}>
          {row.code}
        </button>
      )
    },
    {
      key: 'name',
      title: '设备名称 / 型号',
      render: (row) => (
        <div>
          <div>{row.name}</div>
          <div className="small muted">{[row.manufacturer, row.model].filter(Boolean).join(' · ') || '-'}</div>
        </div>
      )
    },
    {
      key: 'station_name',
      title: '安装位置',
      render: (row) =>
        row.station_name ? (
          <div>
            <div>
              <span className="mono small">{row.station_code}</span> {row.station_name}
            </div>
            <div className="small muted">{row.install_location || '未填写具体位置'}</div>
          </div>
        ) : (
          <span className="muted">未安装</span>
        )
    },
    {
      key: 'calibration_interval_days',
      title: '校准周期',
      align: 'right',
      className: 'cell-nowrap',
      render: (row) => `${row.calibration_interval_days} 天`
    },
    {
      key: 'last_calibration_at',
      title: '最近校准',
      className: 'cell-nowrap',
      render: (row) => formatDateTime(row.last_calibration_at)
    },
    {
      key: 'status',
      title: '状态',
      className: 'cell-nowrap',
      render: (row) => <Tag tone={DEVICE_STATUS_TONE[row.status]}>{row.status_label}</Tag>
    },
    {
      key: 'stats',
      title: '数据量',
      align: 'right',
      className: 'cell-nowrap',
      render: (row) => {
        const stats = row.stats || {}
        return (
          <div>
            <div>{stats.measurement_count ?? 0} 条</div>
            {stats.invalid_count ? (
              <div className="small danger-text">无效 {stats.invalid_count}</div>
            ) : null}
          </div>
        )
      }
    },
    {
      key: 'actions',
      title: '操作',
      align: 'right',
      className: 'cell-nowrap',
      render: (row) => (
        <div className="inline">
          <button type="button" className="btn btn-sm" onClick={() => onDetail(row)}>
            详情
          </button>
          <button type="button" className="btn btn-sm" onClick={() => onCalibrate(row)}>
            校准
          </button>
          <button type="button" className="btn btn-sm" onClick={() => onEdit(row)}>
            编辑
          </button>
          <button type="button" className="btn btn-sm btn-danger" onClick={() => onDelete(row)}>
            删除
          </button>
        </div>
      )
    }
  ]

  return (
    <DataTable
      columns={columns}
      rows={rows}
      loading={loading}
      emptyText="暂无设备档案, 点击右上角登记第一台设备"
      emptyIcon="🛠️"
    />
  )
}
