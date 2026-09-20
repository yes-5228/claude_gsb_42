import { useEffect, useState } from 'react'
import Modal from '../../../components/common/Modal.jsx'
import { Field, Input, Select, Textarea } from '../../../components/common/FormField.jsx'
import { Alert } from '../../../components/common/Feedback.jsx'
import {
  CALIBRATION_RESULT_LABELS,
  CALIBRATION_STATUS_LABELS
} from '../../../constants/index.js'

function toDateTimeLocal(value) {
  if (!value) return ''
  return String(value).replace(' ', 'T').slice(0, 16)
}

const EMPTY = {
  started_at: '',
  ended_at: '',
  status: 'scheduled',
  result: '',
  agency: '',
  operator: '',
  certificate_no: '',
  note: ''
}

function toForm(record) {
  if (!record) return { ...EMPTY }
  return {
    started_at: toDateTimeLocal(record.started_at),
    ended_at: toDateTimeLocal(record.ended_at),
    status: record.status,
    result: record.result || '',
    agency: record.agency || '',
    operator: record.operator || '',
    certificate_no: record.certificate_no || '',
    note: record.note || ''
  }
}

export default function CalibrationFormModal({ open, device, record, onClose, onSubmit }) {
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open) return
    setForm(toForm(record))
    setErrors({})
    setMessage(null)
  }, [open, record])

  const set = (key) => (event) => {
    setForm({ ...form, [key]: event.target.value })
    setErrors((prev) => ({ ...prev, [key]: undefined }))
  }

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setMessage(null)
    try {
      await onSubmit({
        ...form,
        result: form.result || null,
        agency: form.agency || null,
        operator: form.operator || null,
        certificate_no: form.certificate_no || null,
        note: form.note || null
      })
    } catch (error) {
      setErrors(error.fields || {})
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  const terminal = record && ['completed', 'cancelled'].includes(record.status)

  return (
    <Modal
      open={open}
      title={record ? `编辑校准记录 #${record.id}` : `登记校准记录 · ${device?.code || ''}`}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose} disabled={busy}>
            取消
          </button>
          <button type="submit" form="calibration-form" className="btn btn-primary" disabled={busy}>
            {busy ? '保存中...' : '保存'}
          </button>
        </>
      }
    >
      <form id="calibration-form" className="stack" onSubmit={submit}>
        {message ? <Alert tone="error">{message}</Alert> : null}
        {terminal ? (
          <Alert tone="info">该校准记录已完结, 不能再修改状态; 如需调整请删除后重新登记。</Alert>
        ) : null}
        <div className="form-grid">
          <Field label="校准开始时间" required error={errors.started_at}>
            <Input type="datetime-local" value={form.started_at} onChange={set('started_at')} invalid={Boolean(errors.started_at)} />
          </Field>
          <Field label="校准结束时间" required error={errors.ended_at} hint="必须晚于开始时间">
            <Input type="datetime-local" value={form.ended_at} onChange={set('ended_at')} invalid={Boolean(errors.ended_at)} />
          </Field>
          <Field label="校准状态" required error={errors.status}>
            <Select
              value={form.status}
              onChange={set('status')}
              disabled={terminal}
              options={Object.entries(CALIBRATION_STATUS_LABELS)
                // 新建时不允许直接登记为已完成(需补结果), 由保存校验兜底
                .map(([value, label]) => ({ value, label }))}
            />
          </Field>
          <Field label="校准结果" error={errors.result} hint="状态为“已完成”时必填">
            <Select
              value={form.result}
              onChange={set('result')}
              placeholder="校准未完成"
              options={Object.entries(CALIBRATION_RESULT_LABELS).map(([value, label]) => ({ value, label }))}
            />
          </Field>
          <Field label="校准机构" error={errors.agency}>
            <Input value={form.agency} onChange={set('agency')} placeholder="如: 市计量质量检测研究院" />
          </Field>
          <Field label="校准人员" error={errors.operator}>
            <Input value={form.operator} onChange={set('operator')} />
          </Field>
          <Field label="证书编号" error={errors.certificate_no} className="span-2">
            <Input value={form.certificate_no} onChange={set('certificate_no')} placeholder="如: CAL-2026-0001" />
          </Field>
          <Field label="校准说明" error={errors.note} className="span-2">
            <Textarea
              value={form.note}
              onChange={set('note')}
              placeholder="校准项目、示值误差、期间数据处理方式等。校准时段内录入的监测数据将保留并标记为无效, 不参与达标率统计"
            />
          </Field>
        </div>
      </form>
    </Modal>
  )
}
