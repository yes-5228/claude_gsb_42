import http, { toParams } from './client.js'

export const listDevices = (params) => http.get('/devices', { params: toParams(params) })
export const getDevice = (id) => http.get(`/devices/${id}`)
export const createDevice = (payload) => http.post('/devices/', payload)
export const updateDevice = (id, payload) => http.put(`/devices/${id}`, payload)
export const deleteDevice = (id) => http.delete(`/devices/${id}`)
export const deviceOptions = (stationId) =>
  http.get('/devices/options', { params: toParams({ station_id: stationId }) })
export const deviceSummary = () => http.get('/devices/summary')

export const listCalibrations = (params) =>
  http.get('/devices/calibrations', { params: toParams(params) })
export const startCalibration = (deviceId, payload) =>
  http.post(`/devices/${deviceId}/calibrations`, payload)
export const finishCalibration = (recordId, payload) =>
  http.post(`/devices/calibrations/${recordId}/finish`, payload)

export const deviceAvailability = (deviceId, measuredAt) =>
  http.get('/measurements/device-availability', {
    params: toParams({ device_id: deviceId, measured_at: measuredAt })
  })
