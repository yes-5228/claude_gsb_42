import http, { toParams } from './client.js'

export const listDevices = (params) => http.get('/devices', { params: toParams(params) })
export const getDevice = (id) => http.get(`/devices/${id}`)
export const createDevice = (payload) => http.post('/devices', payload)
export const updateDevice = (id, payload) => http.put(`/devices/${id}`, payload)
export const deleteDevice = (id) => http.delete(`/devices/${id}`)
export const deviceOptions = (stationId) =>
  http.get('/devices/options', { params: toParams({ station_id: stationId }) })
export const deviceAvailability = (params) =>
  http.get('/devices/availability', { params: toParams(params) })

export const listCalibrations = (deviceId, params) =>
  http.get(`/devices/${deviceId}/calibrations`, { params: toParams(params) })
export const createCalibration = (deviceId, payload) =>
  http.post(`/devices/${deviceId}/calibrations`, payload)
export const updateCalibration = (id, payload) => http.put(`/devices/calibrations/${id}`, payload)
export const deleteCalibration = (id) => http.delete(`/devices/calibrations/${id}`)
