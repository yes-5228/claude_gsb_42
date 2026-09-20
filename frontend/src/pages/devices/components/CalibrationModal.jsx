import { useEffect, useState } from 'react'
import Modal from '../../../components/common/Modal.jsx'
import { Field, Input, Select, Textarea } from '../../../components/common/FormField.jsx'
import { Alert } from '../../../components/common/Feedback.jsx'
import Tag from '../../../components/common/Tag.jsx'
import { DEVICE_STATUS_TONE } from '../../../constants/index.js'
import { toDateTimeInput } from '../../../utils/format.js'

const RESULT_OPTIONS = [
  { value: 'pass', label: '合格' },
  { value: 'fail', label: '不合格' }
]

const EMPTY_START = {
  started_at: toDateTimeInput(),
  calibrator: '',
  organization: '',
  note: ''
}

export default function CalibrationModal({ device, onClose, onStarted, onFinished }) {
  const [form, setForm] = useState(EMPTY_START)
  const [errors, setErrors] = useState({})
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setForm(EMPTY_START)
    setErrors({})
    setMessage(null)
  }, [device?.id])

  if (!device) return null

  // 列表给出的状态为动态状态; 进行中的校准取详情里 active 的记录
  const activeCalibration = (device.calibrations || []).find((item) => item.active)
  const isCalibrating = device.status === 'calibrating' || Boolean(activeCalibration)

  const set = (key) => (event) => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value
    setForm({ ...form, [key]: value })
    setErrors((prev) => ({ ...prev, [key]: undefined }))
  }

  const start = async (event) => {
    event.preventDefault()
    setBusy(true)
    setMessage(null)
    try {
      await onStarted(device.id, {
        started_at: form.started_at,
        calibrator: form.calibrator || null,
        organization: form.organization || null,
        note: form.note || null
      })
    } catch (error) {
      setErrors(error.fields || {})
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  const finish = async (event) => {
    event.preventDefault()
    setBusy(true)
    setMessage(null)
    try {
      await onFinished(activeCalibration.id, {
        finished_at: form.finished_at || toDateTimeInput(),
        result: form.result || 'pass',
        calibrator: form.calibrator || activeCalibration.calibrator || null,
        organization: form.organization || activeCalibration.organization || null,
        note: form.note || activeCalibration.note || null
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
      open={Boolean(device)}
      title={`设备校准 · ${device.code} ${device.name}`}
      onClose={onClose}
      footer={
        <button type="button" className="btn" onClick={onClose} disabled={busy}>
          关闭
        </button>
      }
    >
      <div className="stack">
        <div className="inline">
          <Tag tone={DEVICE_STATUS_TONE[device.status]}>{device.status_label}</Tag>
          <span className="small muted">
            校准周期 {device.calibration_interval_days} 天 · 最近校准{' '}
            {device.last_calibration_at ? device.last_calibration_at.replace('T', ' ').slice(0, 16) : '无'}
          </span>
        </div>

        {message ? <Alert tone="error">{message}</Alert> : null}

        {isCalibrating ? (
          <Alert tone="warning">
            该设备存在进行中的校准
            {activeCalibration
              ? ` (开始于 ${activeCalibration.started_at.replace('T', ' ').slice(0, 16)})`
              : ''}
            , 校准期间录入的数据将保留但标记为<strong>无效</strong>, 不参与达标率统计。校准完成后请在此登记结束。
          </Alert>
        ) : (
          <Alert tone="info">
            登记校准开始后, 设备将标记为<strong>校准中(不可用)</strong>; 校准时间段内录入该设备的数据会自动标记为无效。
          </Alert>
        )}

        <form onSubmit={isCalibrating ? finish : start} className="stack">
          <div className="form-grid">
            {isCalibrating ? (
              <Field label="校准结束时间" required error={errors.finished_at}>
                <Input
                  type="datetime-local"
                  value={form.finished_at || toDateTimeInput()}
                  onChange={set('finished_at')}
                  invalid={Boolean(errors.finished_at)}
                />
              </Field>
            ) : (
              <Field label="校准开始时间" required error={errors.started_at}>
                <Input
                  type="datetime-local"
                  value={form.started_at}
                  onChange={set('started_at')}
                  invalid={Boolean(errors.started_at)}
                />
              </Field>
            )}
            {isCalibrating ? (
              <Field label="校准结果" required error={errors.result}>
                <Select value={form.result || 'pass'} onChange={set('result')} options={RESULT_OPTIONS} />
              </Field>
            ) : null}
            <Field label="校准人员" error={errors.calibrator}>
              <Input value={form.calibrator} onChange={set('calibrator')} placeholder="如: 王敏" />
            </Field>
            <Field label="校准机构" error={errors.organization}>
              <Input value={form.organization} onChange={set('organization')} placeholder="如: 市计量检测院" />
            </Field>
            <Field label="校准说明" className="span-2" error={errors.note}>
              <Textarea
                value={form.note}
                onChange={set('note')}
                placeholder={isCalibrating ? '校准结论、示值误差、整改要求等' : '校准原因、依据规范等'}
              />
            </Field>
          </div>
          <div>
            {isCalibrating ? (
              <button type="submit" className="btn btn-primary" disabled={busy}>
                {busy ? '提交中...' : '结束校准并恢复可用'}
              </button>
            ) : (
              <button type="submit" className="btn btn-primary" disabled={busy}>
                {busy ? '提交中...' : '登记校准开始'}
              </button>
            )}
          </div>
          {isCalibrating ? (
            <div className="small muted">
              结束校准后系统会自动重算该设备历史数据: 已闭合校准窗口内的数据保持无效, 窗口外恢复有效。
            </div>
          ) : null}
        </form>
      </div>
    </Modal>
  )
}
