import { useCallback, useState } from 'react'
import { getDevice } from '../../../api/devices.js'
import Modal from '../../../components/common/Modal.jsx'
import Tag from '../../../components/common/Tag.jsx'
import DataTable from '../../../components/common/DataTable.jsx'
import ConfirmDialog from '../../../components/common/ConfirmDialog.jsx'
import { Alert, ErrorState, Loading } from '../../../components/common/Feedback.jsx'
import {
  CALIBRATION_RESULT_TONE,
  CALIBRATION_STATUS_TONE,
  DEVICE_STATUS_TONE
} from '../../../constants/index.js'
import { useAsyncData } from '../../../hooks/useAsyncData.js'
import { useToast } from '../../../components/common/ToastProvider.jsx'
import { formatDate, formatDateTime } from '../../../utils/format.js'
import CalibrationFormModal from './CalibrationFormModal.jsx'
import {
  createCalibration,
  deleteCalibration,
  updateCalibration
} from '../../../api/devices.js'

export default function DeviceDetailDrawer({ deviceId, onClose, onChanged }) {
  const loader = useCallback(() => getDevice(deviceId), [deviceId])
  const { data, loading, error, reload } = useAsyncData(loader, { immediate: Boolean(deviceId) })
  const toast = useToast()
  const [formState, setFormState] = useState({ open: false, record: null })
  const [pendingDelete, setPendingDelete] = useState(null)
  const [busy, setBusy] = useState(false)

  const open = Boolean(deviceId)
  const runtime = data?.runtime

  const handleSubmit = async (payload) => {
    if (formState.record) {
      await updateCalibration(formState.record.id, payload)
      toast.success('校准记录已更新, 相关监测数据有效性已重算')
    } else {
      await createCalibration(data.id, payload)
      toast.success('校准记录已登记, 校准时段内的监测数据已标记为无效')
    }
    setFormState({ open: false, record: null })
    reload()
    onChanged?.()
  }

  const handleDelete = async () => {
    if (!pendingDelete) return
    setBusy(true)
    try {
      await deleteCalibration(pendingDelete.id)
      toast.success('校准记录已删除, 相关监测数据已恢复为有效')
      setPendingDelete(null)
      reload()
      onChanged?.()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  const columns = [
    {
      key: 'started_at',
      title: '校准时间',
      render: (row) => (
        <div className="small">
          <div>{formatDateTime(row.started_at)}</div>
          <div className="muted">至 {formatDateTime(row.ended_at)}</div>
        </div>
      )
    },
    {
      key: 'status',
      title: '状态',
      render: (row) => <Tag tone={CALIBRATION_STATUS_TONE[row.status]}>{row.status_label}</Tag>
    },
    {
      key: 'result',
      title: '结果',
      render: (row) =>
        row.result ? (
          <Tag tone={CALIBRATION_RESULT_TONE[row.result]}>{row.result_label}</Tag>
        ) : (
          <span className="muted">-</span>
        )
    },
    { key: 'agency', title: '校准机构', render: (row) => row.agency || '-' },
    { key: 'operator', title: '校准人', render: (row) => row.operator || '-' },
    { key: 'certificate_no', title: '证书编号', className: 'mono small', render: (row) => row.certificate_no || '-' },
    {
      key: 'actions',
      title: '操作',
      align: 'right',
      render: (row) => (
        <div className="btn-group">
          <button type="button" className="btn btn-sm" onClick={() => setFormState({ open: true, record: row })}>
            编辑
          </button>
          <button type="button" className="btn btn-sm btn-danger" onClick={() => setPendingDelete(row)}>
            删除
          </button>
        </div>
      )
    }
  ]

  return (
    <>
      <Modal
        open={open}
        drawer
        title="设备档案与校准管理"
        onClose={onClose}
        footer={
          <>
            <button type="button" className="btn" onClick={onClose}>
              关闭
            </button>
            {data ? (
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setFormState({ open: true, record: null })}
              >
                + 登记校准记录
              </button>
            ) : null}
          </>
        }
      >
        {loading && !data ? <Loading /> : null}
        {error && !data ? <ErrorState error={error} /> : null}
        {data ? (
          <div className="stack">
            <div className="inline">
              <h3 style={{ margin: 0 }}>{data.name}</h3>
              <Tag tone={DEVICE_STATUS_TONE[data.status]}>{data.status_label}</Tag>
              {runtime?.available ? (
                <Tag tone="success">{runtime.state_label}</Tag>
              ) : (
                <Tag tone="danger">{runtime.state_label}</Tag>
              )}
            </div>

            {runtime?.state === 'calibrating' && runtime.calibration ? (
              <Alert tone="error">
                设备正在校准中 ({formatDateTime(runtime.calibration.started_at)} ~{' '}
                {formatDateTime(runtime.calibration.ended_at)}), 此期间录入的监测数据将保留并标记为“无效”,
                不参与达标率统计, 也不会生成超标记录。
              </Alert>
            ) : (
              <Alert tone="info">
                校准期间该设备标记为不可用; 校准时段内录入的数据保留但标记为无效, 自动从达标率统计中剔除。
              </Alert>
            )}

            <dl className="kv">
              <dt>设备编码</dt>
              <dd className="mono">{data.code}</dd>
              <dt>所属监测点</dt>
              <dd>{data.station_name} <span className="muted mono small">({data.station_code})</span></dd>
              <dt>监测因子</dt>
              <dd>{data.pollutant_label}</dd>
              <dt>厂家 / 型号</dt>
              <dd>{data.manufacturer || '-'} {data.model ? `· ${data.model}` : ''}</dd>
              <dt>出厂编号</dt>
              <dd>{data.serial_no || '-'}</dd>
              <dt>量程</dt>
              <dd className="mono">
                {data.measure_min ?? '−∞'} ~ {data.measure_max ?? '+∞'} {data.unit}
              </dd>
              <dt>安装位置</dt>
              <dd>{data.location || '-'}</dd>
              <dt>校准周期</dt>
              <dd>{data.calibration_interval_days} 天</dd>
              <dt>安装日期</dt>
              <dd>{formatDate(data.installed_at)}</dd>
              <dt>备注</dt>
              <dd>{data.remark || '-'}</dd>
            </dl>

            <div className="card">
              <div className="card-header">
                <h3>校准记录</h3>
                <span className="hint">新增 / 修改 / 删除校准记录会自动重算该因子历史数据的有效性</span>
              </div>
              <DataTable
                columns={columns}
                rows={data.calibrations || []}
                emptyText="暂无校准记录, 点击右下角登记首次校准"
                emptyIcon="🧪"
              />
            </div>
          </div>
        ) : null}
      </Modal>

      <CalibrationFormModal
        open={formState.open}
        device={data}
        record={formState.record}
        onClose={() => setFormState({ open: false, record: null })}
        onSubmit={handleSubmit}
      />

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        danger
        busy={busy}
        title="删除校准记录"
        message={`确认删除校准记录 #${pendingDelete?.id || ''} 吗?`}
        detail="删除后该校准时段内的监测数据将恢复为有效, 若超过限值会重新生成超标待标注记录。"
        confirmText="确认删除"
        onConfirm={handleDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </>
  )
}
