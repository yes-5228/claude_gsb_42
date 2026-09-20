import { useCallback, useState } from 'react'
import {
  createDevice,
  deleteDevice,
  listDevices,
  updateDevice
} from '../../api/devices.js'
import ConfirmDialog from '../../components/common/ConfirmDialog.jsx'
import Pagination from '../../components/common/Pagination.jsx'
import { SectionCard } from '../../components/common/Card.jsx'
import StatCard from '../../components/common/StatCard.jsx'
import { Alert } from '../../components/common/Feedback.jsx'
import { useToast } from '../../components/common/ToastProvider.jsx'
import { useListQuery } from '../../hooks/useListQuery.js'
import DeviceDetailDrawer from './components/DeviceDetailDrawer.jsx'
import DeviceFilters from './components/DeviceFilters.jsx'
import DeviceFormModal from './components/DeviceFormModal.jsx'
import DeviceTable from './components/DeviceTable.jsx'

const INITIAL_FILTERS = { keyword: '', station_id: '', pollutant: '', status: '', area: '' }

export default function DevicesPage() {
  const toast = useToast()
  const query = useListQuery(listDevices, INITIAL_FILTERS)
  const [formState, setFormState] = useState({ open: false, device: null })
  const [detailId, setDetailId] = useState(null)
  const [pendingDelete, setPendingDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)

  const summary = query.data?.summary

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
      query.reload()
    },
    [formState.device, query, toast]
  )

  const handleDelete = useCallback(async () => {
    if (!pendingDelete) return
    setDeleting(true)
    try {
      await deleteDevice(pendingDelete.id)
      toast.success(
        `设备 ${pendingDelete.code} 已删除, 其历史监测数据保留, 校准记录一并清除`
      )
      setPendingDelete(null)
      query.reload()
    } catch (error) {
      toast.error(error.message)
    } finally {
      setDeleting(false)
    }
  }, [pendingDelete, query, toast])

  return (
    <>
      <div className="stat-grid">
        <StatCard label="设备总数" value={summary?.total ?? '-'} foot="已登记的监测分析仪/传感器" />
        <StatCard
          label="校准中·不可用"
          value={summary?.calibrating_count ?? '-'}
          tone={summary?.calibrating_count ? 'danger' : undefined}
          foot="校准期间录入的数据标记为无效"
        />
        <StatCard
          label="30 天内到期"
          value={summary?.due_soon_count ?? '-'}
          tone={summary?.due_soon_count ? 'warning' : undefined}
          foot="按校准周期计算, 请提前安排校准"
        />
        <StatCard
          label="已逾期"
          value={summary?.overdue_count ?? '-'}
          tone={summary?.overdue_count ? 'danger' : undefined}
          foot="超过校准周期仍未完成校准"
        />
      </div>

      <DeviceFilters
        value={query.filters}
        loading={query.loading}
        onSubmit={(next) => query.setFilters(next)}
        onReset={() => query.setFilters(INITIAL_FILTERS)}
      />

      {query.error ? <Alert tone="error">{query.error.message}</Alert> : null}

      <SectionCard
        title="设备清单"
        hint="登记设备档案、量程、安装位置与校准周期; 点击“校准”维护校准记录"
        actions={
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setFormState({ open: true, device: null })}
          >
            + 新增设备
          </button>
        }
      >
        <DeviceTable
          rows={query.items}
          loading={query.loading}
          onDetail={(row) => setDetailId(row.id)}
          onEdit={(row) => setFormState({ open: true, device: row })}
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
        onChanged={query.reload}
      />

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        danger
        busy={deleting}
        title="删除监测设备"
        message={`确认删除设备「${pendingDelete?.name || ''}」吗?`}
        detail="设备的校准记录将一并删除; 历史监测数据保留(不再关联设备), 且对应时段数据会重新判定有效性。"
        confirmText="确认删除"
        onConfirm={handleDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </>
  )
}
