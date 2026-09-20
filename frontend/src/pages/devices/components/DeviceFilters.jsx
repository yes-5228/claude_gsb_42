import { useEffect, useState } from 'react'
import { FilterPanel } from '../../../components/common/Card.jsx'
import { Field, Input, Select } from '../../../components/common/FormField.jsx'
import { useStationOptions } from '../../../hooks/useOptions.js'

const STATUS_OPTIONS = [
  { value: 'available', label: '可用' },
  { value: 'calibrating', label: '校准中' },
  { value: 'overdue', label: '校准超期' },
  { value: 'retired', label: '停用' }
]

export default function DeviceFilters({ value, loading, onSubmit, onReset }) {
  const [draft, setDraft] = useState(value)
  const { data: stationData } = useStationOptions()

  useEffect(() => {
    setDraft(value)
  }, [value])

  const update = (key) => (event) => setDraft({ ...draft, [key]: event.target.value })

  const resetDraft = { keyword: '', station_id: '', area: '', status: '' }

  return (
    <FilterPanel
      loading={loading}
      onSearch={() => onSubmit(draft)}
      onReset={() => {
        setDraft(resetDraft)
        onReset()
      }}
    >
      <Field label="关键字">
        <Input
          value={draft.keyword || ''}
          onChange={update('keyword')}
          placeholder="设备编码 / 名称 / 型号"
        />
      </Field>
      <Field label="安装监测点">
        <Select
          value={draft.station_id || ''}
          onChange={update('station_id')}
          placeholder="全部监测点"
          options={(stationData?.items ?? []).map((item) => ({
            value: String(item.id),
            label: `${item.code} ${item.name}`
          }))}
        />
      </Field>
      <Field label="所属区域">
        <Input value={draft.area || ''} onChange={update('area')} placeholder="如: 福田区" />
      </Field>
      <Field label="设备状态">
        <Select value={draft.status || ''} onChange={update('status')} placeholder="全部状态" options={STATUS_OPTIONS} />
      </Field>
    </FilterPanel>
  )
}
