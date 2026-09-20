import { useEffect, useState } from 'react'
import { FilterPanel } from '../../../components/common/Card.jsx'
import { Field, Input, Select } from '../../../components/common/FormField.jsx'
import { deviceOptions as fetchDeviceOptions } from '../../../api/devices.js'
import { usePollutantMeta, useStationOptions } from '../../../hooks/useOptions.js'

const PERIODS = [
  { value: 'hourly', label: '小时均值' },
  { value: 'daily', label: '日均值' }
]

const EXCEEDED_OPTIONS = [
  { value: 'true', label: '仅超标' },
  { value: 'false', label: '仅达标' }
]

const VALID_OPTIONS = [
  { value: 'true', label: '仅有效' },
  { value: 'false', label: '仅无效(校准期)' }
]

const ANNOTATION_OPTIONS = [
  { value: 'pending', label: '待标注' },
  { value: 'confirmed', label: '已确认' },
  { value: 'ignored', label: '已忽略' }
]

const SOURCE_OPTIONS = [
  { value: 'manual', label: '手工录入' },
  { value: 'device', label: '设备上传' },
  { value: 'import', label: '历史导入' }
]

const RESET_DRAFT = {
  keyword: '', station_id: '', device_id: '', area: '', pollutant: '', period: '',
  is_exceeded: '', is_valid: '', exceedance_status: '', data_source: '',
  date_from: '', date_to: '', min_value: '', max_value: ''
}

export default function QueryFilters({ value, loading, onSubmit, onReset }) {
  const [draft, setDraft] = useState(value)
  const [deviceItems, setDeviceItems] = useState([])
  const { data: stationData } = useStationOptions()
  const { data: pollutantData } = usePollutantMeta()

  useEffect(() => {
    setDraft(value)
  }, [value])

  useEffect(() => {
    let cancelled = false
    fetchDeviceOptions(draft.station_id || undefined)
      .then((payload) => {
        if (!cancelled) setDeviceItems(payload.items || [])
      })
      .catch(() => {
        if (!cancelled) setDeviceItems([])
      })
    return () => {
      cancelled = true
    }
  }, [draft.station_id])

  const update = (key) => (event) =>
    setDraft((prev) => ({ ...prev, [key]: event.target.value, ...(key === 'station_id' ? { device_id: '' } : {}) }))

  return (
    <FilterPanel
      loading={loading}
      onSearch={() => onSubmit(draft)}
      onReset={() => {
        setDraft(RESET_DRAFT)
        onReset()
      }}
    >
      <Field label="关键字">
        <Input
          placeholder="监测点名称 / 编码 / 地址"
          value={draft.keyword || ''}
          onChange={update('keyword')}
          onKeyDown={(event) => event.key === 'Enter' && onSubmit(draft)}
        />
      </Field>
      <Field label="监测点">
        <Select
          value={draft.station_id || ''}
          onChange={update('station_id')}
          placeholder="全部监测点"
          options={(stationData?.items ?? []).map((item) => ({ value: String(item.id), label: `${item.code} ${item.name}` }))}
        />
      </Field>
      <Field label="监测设备">
        <Select
          value={draft.device_id || ''}
          onChange={update('device_id')}
          placeholder={draft.station_id ? '全部设备' : '先选择监测点'}
          options={deviceItems.map((item) => ({
            value: String(item.id),
            label: `${item.code} ${item.name}`
          }))}
        />
      </Field>
      <Field label="所属区域">
        <Select
          value={draft.area || ''}
          onChange={update('area')}
          placeholder="全部区域"
          options={(stationData?.areas ?? []).map((area) => ({ value: area, label: area }))}
        />
      </Field>
      <Field label="监测因子">
        <Select
          value={draft.pollutant || ''}
          onChange={update('pollutant')}
          placeholder="全部因子"
          options={(pollutantData?.items ?? []).map((item) => ({ value: item.code, label: item.label }))}
        />
      </Field>
      <Field label="数据周期">
        <Select value={draft.period || ''} onChange={update('period')} placeholder="全部周期" options={PERIODS} />
      </Field>
      <Field label="是否超标">
        <Select value={draft.is_exceeded || ''} onChange={update('is_exceeded')} placeholder="全部" options={EXCEEDED_OPTIONS} />
      </Field>
      <Field label="数据有效性">
        <Select value={draft.is_valid || ''} onChange={update('is_valid')} placeholder="全部" options={VALID_OPTIONS} />
      </Field>
      <Field label="标注状态">
        <Select
          value={draft.exceedance_status || ''}
          onChange={update('exceedance_status')}
          placeholder="全部 (仅筛选超标记录)"
          options={ANNOTATION_OPTIONS}
        />
      </Field>
      <Field label="数据来源">
        <Select value={draft.data_source || ''} onChange={update('data_source')} placeholder="全部来源" options={SOURCE_OPTIONS} />
      </Field>
      <Field label="开始日期">
        <Input type="date" value={draft.date_from || ''} onChange={update('date_from')} />
      </Field>
      <Field label="结束日期">
        <Input type="date" value={draft.date_to || ''} onChange={update('date_to')} />
      </Field>
      <Field label="监测值下限">
        <Input type="number" step="0.01" value={draft.min_value || ''} onChange={update('min_value')} placeholder="不限" />
      </Field>
      <Field label="监测值上限">
        <Input type="number" step="0.01" value={draft.max_value || ''} onChange={update('max_value')} placeholder="不限" />
      </Field>
    </FilterPanel>
  )
}
