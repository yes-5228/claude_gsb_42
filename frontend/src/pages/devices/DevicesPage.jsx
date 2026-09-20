import { useCallback, useState } from 'react'
import {
  createDevice,
  deleteDevice,
  finishCalibration,
  getDevice,
  listDevices,
  startCalibration,
  updateDevice
} from '../../api/devices.js'
import ConfirmDialog from '../../components/common/ConfirmDialog.jsx'
import Pagination from '../../components/common/Pagination.jsx'
import { SectionCard } from '../../components/common/Card.jsx'
import { Alert } from '../../components/common/Feedback.jsx'
import { useToast } from '../../components/common/ToastProvider.jsx'
import { useListQuery } from '../../hooks/useListQuery.js'
import { resetOptionCache } from '../../hooks/useOptions.js'
import CalibrationModal from './components/CalibrationModal.jsx'
import DeviceDetailDrawer from './components/DeviceDetailDrawer.jsx'
import DeviceFilters from './components/DeviceFilters.jsx'
import DeviceFormModal from './components/DeviceFormModal.jsx'
import DeviceTable from './components/DeviceTable.jsx'

const INITIAL_FILTERS = { keyword: '', station_id: '', area: '', status: '' }

export default function DevicesPage() {
  const toast = useToast()
  const query = useListQuery(listDevices, INITIAL_FILTERS)
  const [formState, setFormState] = useState({ open: false, device: null })
  const [detailId, setDetailId] = useState(null)
  const [calibrationDevice, setCalibrationDevice] = useState(null)
  const [pendingDelete, setPendingDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)

  const { reload } = query

  const handleSubmit = useCallback(
    async (payload) => {
      if (formState.device) {
        await updateDevice(formState.device.id, payload)
        toast.success(`设备 ${payload.code} 已更新`)
      } else {
        await createDevice(payload)
        toast.success(`设备 ${payload.code} 已登记`)
      }
      setFormState({ open: false, device: null })
      resetOptionCache()
      reload()
    },
    [formState.device, reload, toast]
  )

  const handleStarted = useCallback(
    async (deviceId, payload) => {
      await startCalibration(deviceId, payload)
      toast.success('已登记校准开始, 设备标记为校准中(不可用)')
      setCalibrationDevice(null)
      reload()
    },
    [reload, toast]
  )

  const handleFinished = useCallback(
    async (recordId, payload) => {
      const result = await finishCalibration(recordId, payload)
      toast.success(
        `校准已结束, 设备恢复可用; 校准窗口内 ${result.invalidated_count} 条数据标记为无效`
      )
      setCalibrationDevice(null)
      setDetailId(null)
      reload()
    },
    [reload, toast]
  )

  const handleDelete = useCallback(async () => {
    if (!pendingDelete) return
    setDeleting(true)
    try {
      const result = await deleteDevice(pendingDelete.id)
      toast.success(
        `已删除设备 ${pendingDelete.code}, ${result.removed.measurements_detached} 条历史数据保留并解除设备关联`
      )
      setPendingDelete(null)
      resetOptionCache()
      reload()
    } catch (error) {
      toast.error(error.message)
    } finally {
      setDeleting(false)
    }
  }, [pendingDelete, reload, toast])

  return (
    <>
      <Alert tone="info">
        校准期间设备标记为<strong>不可用</strong>, 该时段录入的数据保留但自动标记为<strong>无效</strong>,
        不参与达标率统计; 校准合格结束后设备恢复可用。
      </Alert>

      <DeviceFilters
        value={query.filters}
        loading={query.loading}
        onSubmit={(next) => query.setFilters(next)}
        onReset={() => query.setFilters(INITIAL_FILTERS)}
      />

      {query.error ? <Alert tone="error">{query.error.message}</Alert> : null}

      <SectionCard
        title="设备清单"
        hint="设备档案、量程、安装位置与校准周期统一在此维护"
        actions={
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setFormState({ open: true, device: null })}
          >
            + 登记设备
          </button>
        }
      >
        <DeviceTable
          rows={query.items}
          loading={query.loading}
          onDetail={(row) => setDetailId(row.id)}
          onEdit={(row) => setFormState({ open: true, device: row })}
          onCalibrate={(row) => {
            // 列表行没有校准明细, 拉取详情以获取进行中的校准记录
            getDevice(row.id).then((detail) => setCalibrationDevice(detail))
          }}
          onDelete={(row) => setPendingDelete(row)}
        />
        <Pagination
          page={query.page}
          pages={query.pages}
          total={query.total}
          pageSize={query.pageSize}
          onPageChange={query.setPage}
          onPageSizeChange={query.setPageSize}
        />
      </SectionCard>

      <DeviceFormModal
        open={formState.open}
        device={formState.device}
        onClose={() => setFormState({ open: false, device: null })}
        onSubmit={handleSubmit}
      />

      <DeviceDetailDrawer
        deviceId={detailId}
        onClose={() => setDetailId(null)}
        onEdit={(device) => {
          setDetailId(null)
          setFormState({ open: true, device })
        }}
        onCalibrate={(device) => {
          setDetailId(null)
          setCalibrationDevice(device)
        }}
      />

      <CalibrationModal
        device={calibrationDevice}
        onClose={() => setCalibrationDevice(null)}
        onStarted={handleStarted}
        onFinished={handleFinished}
      />

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        danger
        busy={deleting}
        title="删除设备档案"
        message={`确认删除设备「${pendingDelete?.name || ''}」(${pendingDelete?.code || ''})吗?`}
        detail="设备下的校准记录将一并删除; 历史监测数据会保留, 但解除与该设备的关联。"
        confirmText="确认删除"
        onConfirm={handleDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </>
  )
}
