import { useEffect, useState } from 'react'
import Modal from '../../../components/common/Modal.jsx'
import { Field, Input, Select, Textarea } from '../../../components/common/FormField.jsx'
import { Alert } from '../../../components/common/Feedback.jsx'
import Tag from '../../../components/common/Tag.jsx'
import { useStationOptions } from '../../../hooks/useOptions.js'
import { usePollutantMeta } from '../../../hooks/useOptions.js'
import { formatNumber } from '../../../utils/format.js'

const STATUS_OPTIONS = [
  { value: 'available', label: '可用' },
  { value: 'retired', label: '停用' }
]

const EMPTY = {
  code: '',
  name: '',
  model: '',
  manufacturer: '',
  station_id: '',
  install_location: '',
  installed_at: '',
  status: 'available',
  calibration_interval_days: 365,
  last_calibration_at: '',
  remark: ''
}

function toForm(device) {
  if (!device) return { ...EMPTY, ranges: {} }
  const ranges = {}
  ;(device.ranges || []).forEach((item) => {
    ranges[item.pollutant] = {
      min_value: item.min_value ?? '',
      max_value: item.max_value ?? '',
      unit: item.unit || ''
    }
  })
  return {
    code: device.code ?? '',
    name: device.name ?? '',
    model: device.model ?? '',
    manufacturer: device.manufacturer ?? '',
    station_id: device.station_id ? String(device.station_id) : '',
    install_location: device.install_location ?? '',
    installed_at: device.installed_at ?? '',
    status: device.status === 'retired' ? 'retired' : 'available',
    calibration_interval_days: device.calibration_interval_days ?? 365,
    last_calibration_at: device.last_calibration_at ? device.last_calibration_at.slice(0, 16) : '',
    remark: device.remark ?? '',
    ranges
  }
}

export default function DeviceFormModal({ open, device, onClose, onSubmit }) {
  const [form, setForm] = useState(() => toForm(device))
  const [errors, setErrors] = useState({})
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)
  const { data: stationData } = useStationOptions()
  const { data: pollutantData } = usePollutantMeta()

  useEffect(() => {
    if (open) {
      setForm(toForm(device))
      setErrors({})
      setMessage(null)
    }
  }, [open, device])

  const set = (key) => (event) => {
    setForm({ ...form, [key]: event.target.value })
    setErrors((prev) => ({ ...prev, [key]: undefined }))
  }

  const setRange = (code, key) => (event) => {
    const value = event.target.value
    setForm((prev) => ({
      ...prev,
      ranges: {
        ...prev.ranges,
        [code]: { ...(prev.ranges[code] || { min_value: '', max_value: '', unit: '' }), [key]: value }
      }
    }))
  }

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setMessage(null)
    const ranges = []
    for (const item of pollutantData?.items || []) {
      const range = form.ranges[item.code]
      if (!range) continue
      const hasMin = range.min_value !== '' && range.min_value !== null
      const hasMax = range.max_value !== '' && range.max_value !== null
      if (!hasMin && !hasMax && !range.unit) continue
      ranges.push({
        pollutant: item.code,
        min_value: hasMin ? Number(range.min_value) : null,
        max_value: hasMax ? Number(range.max_value) : null,
        unit: range.unit || item.unit
      })
    }
    try {
      await onSubmit({
        ...form,
        station_id: form.station_id ? Number(form.station_id) : null,
        calibration_interval_days: Number(form.calibration_interval_days) || 365,
        installed_at: form.installed_at || null,
        last_calibration_at: form.last_calibration_at || null,
        ranges
      })
    } catch (error) {
      setErrors(error.fields || {})
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      wide
      title={device ? `编辑设备 · ${device.code}` : '登记监测设备'}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose} disabled={busy}>
            取消
          </button>
          <button type="submit" form="device-form" className="btn btn-primary" disabled={busy}>
            {busy ? '保存中...' : '保存'}
          </button>
        </>
      }
    >
      <form id="device-form" className="stack" onSubmit={submit}>
        {message ? <Alert tone="error">{message}</Alert> : null}
        <div className="form-grid">
          <Field label="设备编码" required error={errors.code} hint="全局唯一">
            <Input value={form.code} onChange={set('code')} invalid={Boolean(errors.code)} placeholder="AQMS-001" />
          </Field>
          <Field label="设备名称" required error={errors.name}>
            <Input value={form.name} onChange={set('name')} invalid={Boolean(errors.name)} placeholder="如: 多因子气体分析仪" />
          </Field>
          <Field label="设备型号" error={errors.model}>
            <Input value={form.model} onChange={set('model')} placeholder="如: TH-2000" />
          </Field>
          <Field label="生产厂商" error={errors.manufacturer}>
            <Input value={form.manufacturer} onChange={set('manufacturer')} />
          </Field>
          <Field label="安装监测点" error={errors.station_id}>
            <Select
              value={form.station_id}
              onChange={set('station_id')}
              invalid={Boolean(errors.station_id)}
              placeholder="未安装 (库存设备)"
              options={(stationData?.items ?? []).map((item) => ({
                value: String(item.id),
                label: `${item.code} ${item.name} (${item.area})`
              }))}
            />
          </Field>
          <Field label="安装位置" error={errors.install_location} hint="站内具体安装/采样位置">
            <Input value={form.install_location} onChange={set('install_location')} placeholder="如: 主站房屋顶采样平台" />
          </Field>
          <Field label="安装日期" error={errors.installed_at}>
            <Input type="date" value={form.installed_at} onChange={set('installed_at')} />
          </Field>
          <Field
            label="校准周期(天)"
            required
            error={errors.calibration_interval_days}
            hint="到期未校准将标记为“校准超期”, 数据按无效处理"
          >
            <Input
              type="number"
              min="1"
              value={form.calibration_interval_days}
              onChange={set('calibration_interval_days')}
            />
          </Field>
          <Field label="最近校准时间" error={errors.last_calibration_at} hint="留空表示尚未校准">
            <Input type="datetime-local" value={form.last_calibration_at} onChange={set('last_calibration_at')} />
          </Field>
          <Field label="设备状态" error={errors.status} hint="校准中/超期状态由校准记录自动计算">
            <Select value={form.status} onChange={set('status')} options={STATUS_OPTIONS} />
          </Field>
          <Field label="备注" error={errors.remark} className="span-2">
            <Textarea value={form.remark} onChange={set('remark')} placeholder="设备用途、运维说明等" />
          </Field>
        </div>

        <div className="card" style={{ boxShadow: 'none' }}>
          <div className="card-header">
            <h3>分因子量程</h3>
            <span className="hint">仅填写需要登记量程的因子; 留空表示不限制</span>
          </div>
          <div className="card-body">
            <div className="form-grid">
              {(pollutantData?.items || []).map((pollutant) => {
                const range = form.ranges[pollutant.code] || { min_value: '', max_value: '' }
                return (
                  <div key={pollutant.code} className="field">
                    <label className="field-label">
                      <Tag tone="info">{pollutant.label}</Tag>
                      <span className="muted small" style={{ marginLeft: 6 }}>
                        单位 {pollutant.unit}
                      </span>
                    </label>
                    <div className="inline">
                      <Input
                        type="number"
                        step="0.01"
                        value={range.min_value}
                        onChange={setRange(pollutant.code, 'min_value')}
                        placeholder={`下限 (${formatNumber(0, 0)})`}
                      />
                      <span className="muted">~</span>
                      <Input
                        type="number"
                        step="0.01"
                        value={range.max_value}
                        onChange={setRange(pollutant.code, 'max_value')}
                        placeholder="上限"
                      />
                    </div>
                  </div>
                )
              })}
            </div>
            <div className="small muted" style={{ marginTop: 8 }}>
              录入数值超出量程时界面会给出提示, 但不会阻止保存 (异常值仍记录, 由人工复核)。
            </div>
          </div>
        </div>
      </form>
    </Modal>
  )
}
