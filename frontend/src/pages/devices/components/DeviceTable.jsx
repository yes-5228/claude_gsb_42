import DataTable from '../../../components/common/DataTable.jsx'
import Tag from '../../../components/common/Tag.jsx'
import {
  CALIBRATION_STATUS_TONE,
  DEVICE_STATUS_TONE
} from '../../../constants/index.js'
import { formatDate } from '../../../utils/format.js'

function formatRange(row) {
  if (row.measure_min === null && row.measure_max === null) return <span className="muted">未登记</span>
  const min = row.measure_min === null ? '−∞' : row.measure_min
  const max = row.measure_max === null ? '+∞' : row.measure_max
  return (
    <span className="mono small">
      {min} ~ {max} <span className="muted">{row.unit}</span>
    </span>
  )
}

export default function DeviceTable({ rows, loading, onDetail, onEdit, onDelete }) {
  const columns = [
    { key: 'code', title: '设备编码', className: 'mono cell-nowrap' },
    {
      key: 'name',
      title: '设备名称',
      render: (row) => (
        <div>
          <div className="strong">{row.name}</div>
          <div className="small muted">
            {row.manufacturer || '厂家未登记'} · {row.model || '型号未登记'}
          </div>
        </div>
      )
    },
    {
      key: 'station',
      title: '所属监测点',
      render: (row) => (
        <div>
          <div>{row.station_name}</div>
          <div className="small muted mono">{row.station_code}</div>
        </div>
      )
    },
    { key: 'pollutant_label', title: '因子', className: 'cell-nowrap' },
    { key: 'range', title: '量程', render: (row) => formatRange(row) },
    { key: 'location', title: '安装位置', render: (row) => row.location || <span className="muted">-</span> },
    {
      key: 'calibration_interval_days',
      title: '校准周期',
      align: 'right',
      className: 'cell-nowrap',
      render: (row) => `${row.calibration_interval_days} 天`
    },
    {
      key: 'runtime',
      title: '可用性',
      render: (row) => {
        const runtime = row.runtime || { available: true, state_label: row.status_label }
        return runtime.available ? (
          <Tag tone="success">{runtime.state_label}</Tag>
        ) : (
          <Tag tone={CALIBRATION_STATUS_TONE[runtime.state === 'calibrating' ? 'in_progress' : 'neutral']}>
            {runtime.state_label}
          </Tag>
        )
      }
    },
    {
      key: 'status',
      title: '档案状态',
      render: (row) => <Tag tone={DEVICE_STATUS_TONE[row.status]}>{row.status_label}</Tag>
    },
    {
      key: 'installed_at',
      title: '安装日期',
      className: 'cell-nowrap',
      render: (row) => formatDate(row.installed_at)
    },
    {
      key: 'actions',
      title: '操作',
      align: 'right',
      render: (row) => (
        <div className="btn-group">
          <button type="button" className="btn btn-sm" onClick={() => onDetail(row)}>
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
      emptyText="还没有监测设备档案, 点击右上角新增"
      emptyIcon="🔧"
    />
  )
}
