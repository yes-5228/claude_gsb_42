import { useCallback } from 'react'
import { getDevice } from '../../../api/devices.js'
import Modal from '../../../components/common/Modal.jsx'
import Tag from '../../../components/common/Tag.jsx'
import DataTable from '../../../components/common/DataTable.jsx'
import { ErrorState, Loading } from '../../../components/common/Feedback.jsx'
import { CALIBRATION_RESULT_TONE, DEVICE_STATUS_TONE } from '../../../constants/index.js'
import { useAsyncData } from '../../../hooks/useAsyncData.js'
import { formatDate, formatDateTime, formatNumber } from '../../../utils/format.js'

export default function DeviceDetailDrawer({ deviceId, onClose, onEdit, onCalibrate }) {
  const loader = useCallback(() => getDevice(deviceId), [deviceId])
  const { data, loading, error, reload } = useAsyncData(loader, { immediate: Boolean(deviceId) })

  const open = Boolean(deviceId)

  const rangeColumns = [
    {
      key: 'pollutant',
      title: '监测因子',
      render: (row) => {
        const labels = { PM25: 'PM2.5', PM10: 'PM10', SO2: 'SO₂', NO2: 'NO₂', CO: 'CO', O3: 'O₃' }
        return labels[row.pollutant] || row.pollutant
      }
    },
    {
      key: 'min_value',
      title: '量程下限',
      align: 'right',
      render: (row) => (row.min_value === null ? <span className="muted">不限</span> : formatNumber(row.min_value))
    },
    {
      key: 'max_value',
      title: '量程上限',
      align: 'right',
      render: (row) => (row.max_value === null ? <span className="muted">不限</span> : formatNumber(row.max_value))
    },
    { key: 'unit', title: '单位', render: (row) => row.unit || '-' }
  ]

  const calibrationColumns = [
    {
      key: 'started_at',
      title: '开始时间',
      className: 'cell-nowrap',
      render: (row) => formatDateTime(row.started_at)
    },
    {
      key: 'finished_at',
      title: '结束时间',
      className: 'cell-nowrap',
      render: (row) =>
        row.active ? <Tag tone="warning">校准中</Tag> : formatDateTime(row.finished_at)
    },
    {
      key: 'result',
      title: '结果',
      render: (row) =>
        row.result ? <Tag tone={CALIBRATION_RESULT_TONE[row.result]}>{row.result_label}</Tag> : '-'
    },
    { key: 'calibrator', title: '校准人员', render: (row) => row.calibrator || '-' },
    { key: 'organization', title: '校准机构', render: (row) => row.organization || '-' },
    { key: 'note', title: '说明', render: (row) => row.note || '-' }
  ]

  return (
    <Modal
      open={open}
      drawer
      title="设备详情"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            关闭
          </button>
          {data ? (
            <>
              <button type="button" className="btn" onClick={() => onCalibrate(data)}>
                校准登记
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => {
                  onEdit(data)
                }}
              >
                编辑档案
              </button>
            </>
          ) : null}
        </>
      }
    >
      {loading && !data ? <Loading /> : null}
      {error && !data ? <ErrorState error={error} onRetry={reload} /> : null}
      {data ? (
        <div className="stack">
          <div className="inline">
            <h3 style={{ margin: 0 }}>{data.name}</h3>
            <Tag tone={DEVICE_STATUS_TONE[data.status]}>{data.status_label}</Tag>
          </div>
          <dl className="kv">
            <dt>设备编码</dt>
            <dd className="mono">{data.code}</dd>
            <dt>型号 / 厂商</dt>
            <dd>{[data.model, data.manufacturer].filter(Boolean).join(' · ') || '-'}</dd>
            <dt>安装监测点</dt>
            <dd>
              {data.station_name ? (
                <span>
                  <span className="mono">{data.station_code}</span> {data.station_name}
                </span>
              ) : (
                '未安装'
              )}
            </dd>
            <dt>安装位置</dt>
            <dd>{data.install_location || '-'}</dd>
            <dt>安装日期</dt>
            <dd>{formatDate(data.installed_at)}</dd>
            <dt>校准周期</dt>
            <dd>{data.calibration_interval_days} 天</dd>
            <dt>最近校准</dt>
            <dd>{formatDateTime(data.last_calibration_at)}</dd>
            <dt>累计数据</dt>
            <dd>
              {(data.stats?.measurement_count ?? 0)} 条
              {data.stats?.invalid_count ? (
                <span className="danger-text">（无效 {data.stats.invalid_count} 条）</span>
              ) : null}
            </dd>
            <dt>备注</dt>
            <dd>{data.remark || '-'}</dd>
          </dl>

          <div className="card">
            <div className="card-header">
              <h3>分因子量程</h3>
            </div>
            <DataTable columns={rangeColumns} rows={data.ranges || []} emptyText="未登记量程信息" emptyIcon="📐" />
          </div>

          <div className="card">
            <div className="card-header">
              <h3>校准记录</h3>
              <span className="hint">校准窗口内录入的数据标记为无效</span>
            </div>
            <DataTable
              columns={calibrationColumns}
              rows={data.calibrations || []}
              emptyText="暂无校准记录"
              emptyIcon="🧪"
            />
          </div>
        </div>
      ) : null}
    </Modal>
  )
}
