import { useCallback, useEffect, useMemo, useState } from 'react'
import { createEntries, previewEntries } from '../../../api/measurements.js'
import { SectionCard } from '../../../components/common/Card.jsx'
import { Checkbox, Field, Input, Select } from '../../../components/common/FormField.jsx'
import { Alert, Loading } from '../../../components/common/Feedback.jsx'
import Tag from '../../../components/common/Tag.jsx'
import { useToast } from '../../../components/common/ToastProvider.jsx'
import { usePollutantMeta, useStationOptions } from '../../../hooks/useOptions.js'
import { useDeviceAvailability } from '../../../hooks/useDeviceAvailability.js'
import { formatDateTime, formatNumber, toDateTimeInput } from '../../../utils/format.js'

const PERIODS = [
  { value: 'hourly', label: '小时均值' },
  { value: 'daily', label: '日均值' }
]

const DATA_SOURCES = [
  { value: 'manual', label: '手工录入' },
  { value: 'device', label: '设备上传' },
  { value: 'import', label: '历史导入' }
]

export default function EntryForm({ onPreview, onSubmitted }) {
  const toast = useToast()
  const { data: stationData, loading: stationLoading, error: stationError } = useStationOptions()
  const { data: pollutantData, loading: pollutantLoading } = usePollutantMeta()

  const [form, setForm] = useState({
    station_id: '',
    measured_at: toDateTimeInput(),
    period: 'hourly',
    data_source: 'manual',
    recorder: '',
    remark: '',
    overwrite: false
  })
  const [values, setValues] = useState({})
  const [errors, setErrors] = useState({})
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(null)
  const [evaluations, setEvaluations] = useState({})
  const [acknowledged, setAcknowledged] = useState(false)

  const pollutants = pollutantData?.items ?? []
  const pollutantCodes = useMemo(() => pollutants.map((item) => item.code), [pollutants])

  const availability = useDeviceAvailability({
    stationId: form.station_id ? Number(form.station_id) : '',
    measuredAt: form.measured_at,
    pollutants: pollutantCodes,
    enabled: Boolean(form.station_id && form.measured_at)
  })

  useEffect(() => {
    if (!form.station_id && stationData?.items?.length) {
      setForm((prev) => ({ ...prev, station_id: String(stationData.items[0].id) }))
    }
  }, [stationData, form.station_id])

  // 监测点 / 时刻变化后, 校准期知悉勾选需要重新确认
  useEffect(() => {
    setAcknowledged(false)
  }, [form.station_id, form.measured_at])

  const deviceInfo = useCallback(
    (pollutant) => availability.data?.devices?.[pollutant] ?? null,
    [availability.data]
  )

  const unavailableSelected = useMemo(() => {
    return Object.keys(values)
      .filter((code) => values[code] !== '' && values[code] != null)
      .map((code) => deviceInfo(code))
      .filter((info) => info && !info.available)
  }, [values, deviceInfo])

  const outOfRange = useCallback(
    (pollutant) => {
      const raw = values[pollutant]
      const info = deviceInfo(pollutant)
      if (raw === '' || raw == null || !info) return null
      const number = Number(raw)
      if (Number.isNaN(number)) return null
      if (info.measure_min !== null && info.measure_min !== undefined && number < info.measure_min) {
        return `低于设备量程下限 ${formatNumber(info.measure_min)} ${info.unit || ''}`
      }
      if (info.measure_max !== null && info.measure_max !== undefined && number > info.measure_max) {
        return `高于设备量程上限 ${formatNumber(info.measure_max)} ${info.unit || ''}`
      }
      return null
    },
    [values, deviceInfo]
  )

  const limitHint = useCallback(
    (pollutant) => {
      const limit = pollutant.limits?.[form.period]
      const info = deviceInfo(pollutant.code)
      const parts = []
      if (limit === null || limit === undefined) parts.push('该周期未设限值, 仅记录数值')
      else parts.push(`限值 ${formatNumber(limit)} ${pollutant.unit}`)
      if (info && (info.measure_min !== null || info.measure_max !== null)) {
        parts.push(
          `设备量程 ${formatNumber(info.measure_min)} ~ ${formatNumber(info.measure_max)} ${info.unit || ''}`
        )
      }
      if (info?.location) parts.push(`安装位置: ${info.location}`)
      return parts.join(' · ')
    },
    [form.period, deviceInfo]
  )

  const filled = useMemo(
    () =>
      Object.entries(values).filter(
        ([, raw]) => raw !== '' && raw !== null && raw !== undefined
      ),
    [values]
  )

  const entries = useMemo(
    () => filled.map(([pollutant, raw]) => ({ pollutant, value: Number(raw) })),
    [filled]
  )

  const setField = (key) => (event) => {
    const value = key === 'overwrite' ? event.target.checked : event.target.value
    setForm((prev) => ({ ...prev, [key]: value }))
    setErrors((prev) => ({ ...prev, [key]: undefined }))
  }

  const setValue = (pollutant) => (event) => {
    setValues((prev) => ({ ...prev, [pollutant]: event.target.value }))
    setErrors((prev) => ({ ...prev, [pollutant]: undefined }))
  }

  const validate = () => {
    const next = {}
    if (!form.station_id) next.station_id = '请选择监测点'
    if (!form.measured_at) next.measured_at = '请选择监测时间'
    if (filled.length === 0) next.entries = '至少填写一个因子的监测值'
    filled.forEach(([pollutant, raw]) => {
      const number = Number(raw)
      if (Number.isNaN(number)) next[pollutant] = '监测值必须是数字'
      else if (number < 0) next[pollutant] = '监测值不能为负数'
      else if (number > 10000) next[pollutant] = '监测值超出合理范围, 请检查是否录错'
    })
    setErrors(next)
    if (Object.keys(next).length) {
      setMessage('请先修正表单中标红的问题')
      return false
    }
    if (unavailableSelected.length > 0 && !acknowledged) {
      setMessage('所选时刻存在校准中的设备, 请阅读提示并勾选确认后再提交')
      return false
    }
    setMessage(null)
    return true
  }

  const annotateResults = (result) => {
    result.results.forEach((item) => {
      const info = deviceInfo(item.pollutant)
      item.is_valid = info ? info.available : true
      item.invalid_message = info && !info.available
        ? '设备校准期间数据, 将标记为无效且不参与达标率统计'
        : null
      item.device_code = info?.device_code ?? null
      item.device_name = info?.device_name ?? null
    })
    result.summary.invalid_count = result.results.filter((item) => !item.is_valid).length
    return result
  }

  const runPreview = async () => {
    if (!validate()) return
    setBusy('preview')
    try {
      const result = annotateResults(await previewEntries({ period: form.period, entries }))
      const map = {}
      result.results.forEach((item) => {
        map[item.pollutant] = item
      })
      setEvaluations(map)
      onPreview?.(result)
      if (result.summary.invalid_count > 0) {
        toast.warning(`校验完成: ${result.summary.invalid_count} 项处于设备校准期, 将标记为无效`)
      } else if (result.summary.exceeded_count > 0) {
        toast.warning(`校验完成: ${result.summary.exceeded_count} 个因子超过限值`)
      } else {
        toast.success('校验完成: 所有因子均未超过限值')
      }
    } catch (error) {
      setErrors(error.fields || {})
      setMessage(error.message)
      toast.error(error.message)
    } finally {
      setBusy(null)
    }
  }

  const submit = async () => {
    if (!validate()) return
    setBusy('submit')
    try {
      const result = await createEntries({
        station_id: Number(form.station_id),
        measured_at: form.measured_at,
        period: form.period,
        data_source: form.data_source,
        recorder: form.recorder || null,
        remark: form.remark || null,
        overwrite: form.overwrite,
        entries
      })
      const map = {}
      ;(result.evaluations || []).forEach((item) => {
        map[item.pollutant] = item
      })
      setEvaluations(map)
      setValues({})
      setAcknowledged(false)
      onSubmitted?.(result)
      const written = result.summary.created_count + result.summary.updated_count
      if (result.summary.invalid_count > 0) {
        toast.warning(
          `写入 ${written} 条, 其中 ${result.summary.invalid_count} 条为校准期数据已标记无效(保留但不参与达标统计)`
        )
      } else if (result.summary.exceeded_count > 0) {
        toast.warning(`写入 ${written} 条数据, 其中 ${result.summary.exceeded_count} 项超标已生成待标注记录`)
      } else {
        toast.success(`录入成功, 共写入 ${written} 条数据`)
      }
    } catch (error) {
      setErrors(error.fields || {})
      setMessage(error.message)
      toast.error(error.message)
    } finally {
      setBusy(null)
    }
  }

  if (stationLoading || pollutantLoading) {
    return (
      <SectionCard title="监测数据录入">
        <Loading text="正在加载监测点与监测因子..." />
      </SectionCard>
    )
  }

  const unavailableAll = availability.data?.unavailable ?? []

  return (
    <SectionCard
      title="监测数据录入"
      hint="选择监测点与监测时刻, 一次录入该时刻的各因子浓度"
      actions={<Tag tone="primary">{form.period === 'hourly' ? '小时均值' : '日均值'}</Tag>}
    >
      <div className="stack">
        {stationError ? <Alert tone="error">{stationError.message}</Alert> : null}
        {message ? <Alert tone="error">{message}</Alert> : null}

        {availability.loading ? (
          <Alert tone="info">正在核对该时刻各因子监测设备的可用性...</Alert>
        ) : null}

        {unavailableAll.length > 0 ? (
          <Alert tone="error">
            <div className="stack" style={{ gap: 6 }}>
              <div>
                <strong>⚠ 以下设备在 {formatDateTime(form.measured_at)} 正处于校准期, 标记为不可用:</strong>
              </div>
              {unavailableAll.map((item) => (
                <div key={item.pollutant}>
                  <Tag tone="danger">{item.pollutant === 'PM25' ? 'PM2.5' : item.pollutant}</Tag>{' '}
                  <span className="mono small">{item.device_code}</span> {item.device_name}
                  {item.calibration ? (
                    <span className="small">
                      {' '}· 校准时段 {formatDateTime(item.calibration.started_at)} ~{' '}
                      {formatDateTime(item.calibration.ended_at)}
                    </span>
                  ) : null}
                </div>
              ))}
              <div className="small">
                校准期间仍可录入数据用于留痕, 但数据会自动标记为<strong>“无效”</strong>:
                原始数值保留可查, 不生成超标记录, 并从达标率统计中自动剔除。
              </div>
              <div>
                <Checkbox
                  label="我已知悉上述设备不可用, 仍要提交该时刻数据(将标记为无效)"
                  checked={acknowledged}
                  onChange={(event) => setAcknowledged(event.target.checked)}
                />
              </div>
            </div>
          </Alert>
        ) : null}

        <div className="form-grid">
          <Field label="监测点" required error={errors.station_id}>
            <Select
              value={form.station_id}
              onChange={setField('station_id')}
              invalid={Boolean(errors.station_id)}
              placeholder="请选择监测点"
              options={(stationData?.items ?? []).map((item) => ({
                value: String(item.id),
                label: `${item.code} ${item.name} (${item.area})`
              }))}
            />
          </Field>
          <Field label="监测时间" required error={errors.measured_at} hint="小时数据请填写整点; 切换时刻会重新核对设备校准状态">
            <Input
              type="datetime-local"
              value={form.measured_at}
              onChange={setField('measured_at')}
              invalid={Boolean(errors.measured_at)}
            />
          </Field>
          <Field label="数据周期" required>
            <Select value={form.period} onChange={setField('period')} options={PERIODS} />
          </Field>
          <Field label="数据来源">
            <Select value={form.data_source} onChange={setField('data_source')} options={DATA_SOURCES} />
          </Field>
          <Field label="录入人">
            <Input value={form.recorder} onChange={setField('recorder')} placeholder="如: 张三" />
          </Field>
          <Field label="备注">
            <Input value={form.remark} onChange={setField('remark')} placeholder="选填" />
          </Field>
        </div>

        <div className="card" style={{ boxShadow: 'none' }}>
          <div className="card-header">
            <h3>因子浓度</h3>
            <span className="hint">留空的因子不会写入; 关联设备量程与校准状态见字段提示</span>
          </div>
          <div className="card-body">
            {errors.entries ? <Alert tone="error">{errors.entries}</Alert> : null}
            <div className="form-grid">
              {pollutants.map((pollutant) => {
                const evaluation = evaluations[pollutant.code]
                const info = deviceInfo(pollutant.code)
                const unavailable = info && !info.available
                const rangeError = outOfRange(pollutant.code)
                return (
                  <Field
                    key={pollutant.code}
                    label={`${pollutant.label} (${pollutant.unit})`}
                    error={errors[pollutant.code] || rangeError}
                    hint={limitHint(pollutant)}
                  >
                    <div className="stack" style={{ gap: 6 }}>
                      <div className="inline" style={{ flexWrap: 'nowrap' }}>
                        <Input
                          type="number"
                          step="0.01"
                          min="0"
                          value={values[pollutant.code] ?? ''}
                          onChange={setValue(pollutant.code)}
                          invalid={Boolean(errors[pollutant.code]) || rangeError}
                          placeholder="--"
                        />
                        {unavailable ? <Tag tone="danger" title="校准期间录入将标记为无效">校准中·无效</Tag> : null}
                        {evaluation?.exceeded ? <Tag tone="danger">超标</Tag> : null}
                        {evaluation && !evaluation.exceeded && evaluation.applicable && evaluation.is_valid !== false ? (
                          <Tag tone="success">达标</Tag>
                        ) : null}
                      </div>
                      {unavailable ? (
                        <div className="small" style={{ color: 'var(--danger)' }}>
                          {info.device_code} 校准中
                          {info.calibration
                            ? ` (${formatDateTime(info.calibration.started_at)} ~ ${formatDateTime(info.calibration.ended_at)})`
                            : ''}
                          , 录入后保留但标记无效
                        </div>
                      ) : info ? (
                        <div className="small muted">
                          关联设备: <span className="mono">{info.device_code}</span> {info.device_name}
                        </div>
                      ) : null}
                    </div>
                  </Field>
                )
              })}
            </div>
          </div>
        </div>

        <div>
          <Checkbox
            label="覆盖同一时刻已有数据"
            checked={form.overwrite}
            onChange={setField('overwrite')}
          />
          <div className="small muted" style={{ marginTop: 4 }}>
            勾选后重复提交将更新原记录并重新判定超标与数据有效性
          </div>
        </div>

        <div className="inline">
          <button type="button" className="btn" onClick={runPreview} disabled={busy !== null}>
            {busy === 'preview' ? '校验中...' : '超标校验预览'}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={submit}
            disabled={busy !== null || unavailableSelected.length > 0 && !acknowledged}
          >
            {busy === 'submit' ? '提交中...' : '提交录入'}
          </button>
          <span className="small muted">
            已填写 {filled.length} / {pollutants.length} 个因子
            {unavailableSelected.length > 0 ? ` · ${unavailableSelected.length} 项将标记无效` : ''}
          </span>
        </div>
      </div>
    </SectionCard>
  )
}
