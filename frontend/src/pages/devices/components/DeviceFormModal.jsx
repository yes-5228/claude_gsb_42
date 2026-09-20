import { useEffect, useState } from 'react'
import Modal from '../../../components/common/Modal.jsx'
import { Field, Input, Select, Textarea } from '../../../components/common/FormField.jsx'
import { Alert } from '../../../components/common/Feedback.jsx'
import { usePollutantMeta, useStationOptions } from '../../../hooks/useOptions.js'
import { DEVICE_STATUS_LABELS } from '../../../constants/index.js'

const EMPTY = {
  code: '',
  name: '',
  station_id: '',
  pollutant: 'PM25',
  manufacturer: '',
  model: '',
  serial_no: '',
  measure_min: '',
  measure_max: '',
  unit: '',
  location: '',
  calibration_interval_days: 365,
  status: 'in_service',
  installed_at: '',
  remark: ''
}

function toForm(device) {
  if (!device) return { ...EMPTY }
  return {
    ...EMPTY,
    ...device,
    station_id: device.station_id ? String(device.station_id) : '',
    measure_min: device.measure_min ?? '',
    measure_max: device.measure_max ?? '',
    installed_at: device.installed_at ?? ''
  }
}

export default function DeviceFormModal({ open, device, onClose, onSubmit }) {
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)
  const { data: stationData } = useStationOptions()
  const { data: pollutantData } = usePollutantMeta()

  useEffect(() => {
    if (!open) return
    setForm(toForm(device))
    setErrors({})
    setMessage(null)
  }, [open, device])

  const set = (key) => (event) => {
    const value = event.target.value
    setForm((prev) => {
      const next = { ...prev, [key]: value }
      if (key === 'pollutant') {
        const meta = (pollutantData?.items ?? []).find((item) => item.code === value)
        if (meta && !next.unit) next.unit = meta.unit
      }
      return next
    })
    setErrors((prev) => ({ ...prev, [key]: undefined }))
  }

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setMessage(null)
    try {
      await onSubmit({
        ...form,
        station_id: Number(form.station_id),
        measure_min: form.measure_min === '' ? null : Number(form.measure_min),
        measure_max: form.measure_max === '' ? null : Number(form.measure_max),
        calibration_interval_days: Number(form.calibration_interval_days) || 365,
        unit: form.unit || null,
        installed_at: form.installed_at || null
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
      title={device ? `编辑设备 · ${device.code}` : '新增监测设备'}
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
          <Field label="设备编码" required error={errors.code} hint="全局唯一, 如 AQ-001-PM25">
            <Input value={form.code} onChange={set('code')} invalid={Boolean(errors.code)} placeholder="AQ-001-PM25" />
          </Field>
          <Field label="设备名称" required error={errors.name}>
            <Input value={form.name} onChange={set('name')} invalid={Boolean(errors.name)} placeholder="如: 市民中心 PM2.5 分析仪" />
          </Field>
          <Field label="所属监测点" required error={errors.station_id}>
            <Select
              value={form.station_id}
              onChange={set('station_id')}
              invalid={Boolean(errors.station_id)}
              placeholder="请选择监测点"
              options={(stationData?.items ?? []).map((item) => ({
                value: String(item.id),
                label: `${item.code} ${item.name}`
              }))}
            />
          </Field>
          <Field label="监测因子" required error={errors.pollutant}>
            <Select
              value={form.pollutant}
              onChange={set('pollutant')}
              options={(pollutantData?.items ?? []).map((item) => ({ value: item.code, label: item.label }))}
            />
          </Field>
          <Field label="生产厂家" error={errors.manufacturer}>
            <Input value={form.manufacturer} onChange={set('manufacturer')} placeholder="如: 聚光科技" />
          </Field>
          <Field label="设备型号" error={errors.model}>
            <Input value={form.model} onChange={set('model')} placeholder="如: AQMS-503" />
          </Field>
          <Field label="出厂编号" error={errors.serial_no}>
            <Input value={form.serial_no} onChange={set('serial_no')} />
          </Field>
          <Field label="计量单位" error={errors.unit}>
            <Input value={form.unit} onChange={set('unit')} placeholder="μg/m³ / mg/m³" />
          </Field>
          <Field label="量程下限" error={errors.measure_min} hint="留空表示不限制">
            <Input type="number" step="0.001" value={form.measure_min} onChange={set('measure_min')} invalid={Boolean(errors.measure_min)} />
          </Field>
          <Field label="量程上限" error={errors.measure_max} hint="留空表示不限制">
            <Input type="number" step="0.001" value={form.measure_max} onChange={set('measure_max')} invalid={Boolean(errors.measure_max)} />
          </Field>
          <Field label="安装位置" error={errors.location} hint="如: 站房分析间机柜 A 列 / 采样总管 1 号位">
            <Input value={form.location} onChange={set('location')} placeholder="设备在监测点的具体安装位置" />
          </Field>
          <Field label="校准周期 (天)" required error={errors.calibration_interval_days} hint="到期前 30 天在概览页提醒">
            <Input type="number" min="1" max="3650" value={form.calibration_interval_days} onChange={set('calibration_interval_days')} />
          </Field>
          <Field label="设备状态" required error={errors.status}>
            <Select
              value={form.status}
              onChange={set('status')}
              options={Object.entries(DEVICE_STATUS_LABELS).map(([value, label]) => ({ value, label }))}
            />
          </Field>
          <Field label="安装日期" error={errors.installed_at}>
            <Input type="date" value={form.installed_at} onChange={set('installed_at')} />
          </Field>
          <Field label="备注" error={errors.remark} className="span-2">
            <Textarea value={form.remark} onChange={set('remark')} placeholder="量程精度、运维联系人等" />
          </Field>
        </div>
      </form>
    </Modal>
  )
}
