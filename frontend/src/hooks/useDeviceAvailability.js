import { useCallback, useEffect, useRef, useState } from 'react'
import { deviceAvailability } from '../api/devices.js'

/**
 * Fetch device availability / range / calibration window for one station at a
 * moment in time, keyed by the pollutants the caller cares about.
 */
export function useDeviceAvailability({ stationId, measuredAt, pollutants = [], enabled = true }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const requestId = useRef(0)

  const codes = pollutants.join(',')
  const load = useCallback(async () => {
    if (!enabled || !stationId || !measuredAt) {
      setData(null)
      return
    }
    const current = ++requestId.current
    setLoading(true)
    setError(null)
    try {
      const payload = await deviceAvailability({
        station_id: stationId,
        measured_at: measuredAt,
        pollutants: codes
      })
      if (current === requestId.current) setData(payload)
    } catch (err) {
      if (current === requestId.current) {
        setError(err)
        setData(null)
      }
    } finally {
      if (current === requestId.current) setLoading(false)
    }
  }, [enabled, stationId, measuredAt, codes])

  useEffect(() => {
    load()
  }, [load])

  return { data, loading, error, reload: load }
}
