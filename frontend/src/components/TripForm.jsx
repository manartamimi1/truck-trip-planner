import { useState } from 'react'

const INITIAL_VALUES = {
  current_location: '',
  pickup_location: '',
  dropoff_location: '',
  current_cycle_used: '',
}

const LOCATION_FIELDS = [
  { name: 'current_location', label: 'Current location', placeholder: 'Chicago, IL', step: '01' },
  { name: 'pickup_location', label: 'Pickup location', placeholder: 'Indianapolis, IN', step: '02' },
  { name: 'dropoff_location', label: 'Dropoff location', placeholder: 'Atlanta, GA', step: '03' },
]

function TripForm({ onPlanTrip, loading, requestError, clearRequestError }) {
  const [values, setValues] = useState(INITIAL_VALUES)
  const [errors, setErrors] = useState({})

  function updateValue(event) {
    const { name, value } = event.target
    setValues((current) => ({ ...current, [name]: value }))
    setErrors((current) => ({ ...current, [name]: '' }))
    if (requestError) clearRequestError()
  }

  function validate() {
    const nextErrors = {}
    LOCATION_FIELDS.forEach(({ name, label }) => {
      if (!values[name].trim()) nextErrors[name] = `${label} is required.`
    })

    const rawCycle = values.current_cycle_used.trim()
    const cycle = Number(rawCycle)
    if (!rawCycle) {
      nextErrors.current_cycle_used = 'Enter the cycle hours already used.'
    } else if (!Number.isFinite(cycle)) {
      nextErrors.current_cycle_used = 'Enter a valid number of hours.'
    } else if (cycle < 0 || cycle > 70) {
      nextErrors.current_cycle_used = 'Cycle hours must be between 0 and 70.'
    }
    setErrors(nextErrors)
    return Object.keys(nextErrors).length === 0
  }

  function handleSubmit(event) {
    event.preventDefault()
    if (loading) return
    if (!validate()) return
    onPlanTrip({
      current_location: values.current_location.trim(),
      pickup_location: values.pickup_location.trim(),
      dropoff_location: values.dropoff_location.trim(),
      current_cycle_used: Number(values.current_cycle_used),
    })
  }

  return (
    <form className="panel trip-form" onSubmit={handleSubmit} noValidate>
      <div className="panel-heading">
        <div>
          <p className="eyebrow">ROUTE DETAILS</p>
          <h2>Plan trip</h2>
        </div>
        <span className="required-note"><span aria-hidden="true">*</span> Required</span>
      </div>

      <div className="location-fields">
        {LOCATION_FIELDS.map(({ name, label, placeholder, step }) => (
          <div className="field-group" key={name}>
            <label htmlFor={name}>
              <span className="field-step">{step}</span>
              <span>{label}<span className="required-asterisk" aria-hidden="true"> *</span></span>
            </label>
            <input
              id={name}
              name={name}
              type="text"
              autoComplete="off"
              required
              placeholder={placeholder}
              value={values[name]}
              onChange={updateValue}
              aria-invalid={Boolean(errors[name])}
              aria-describedby={errors[name] ? `${name}-error` : undefined}
            />
            {errors[name] && <p className="field-error" id={`${name}-error`}>{errors[name]}</p>}
          </div>
        ))}
      </div>

      <div className="cycle-field field-group">
        <label htmlFor="current_cycle_used">
          <span>Current cycle used<span className="required-asterisk" aria-hidden="true"> *</span></span>
          <span className="field-unit">HOURS</span>
        </label>
        <div className="number-input-wrap">
          <input
            id="current_cycle_used"
            name="current_cycle_used"
            type="number"
            min="0"
            max="70"
            step="any"
            required
            inputMode="decimal"
            placeholder="15"
            value={values.current_cycle_used}
            onChange={updateValue}
            aria-invalid={Boolean(errors.current_cycle_used)}
            aria-describedby={errors.current_cycle_used ? 'current_cycle_used-error' : 'cycle-help'}
          />
          <span>hrs</span>
        </div>
        <p className="field-help" id="cycle-help">On-duty hours already used in the current 70-hour / 8-day cycle.</p>
        {errors.current_cycle_used && <p className="field-error" id="current_cycle_used-error">{errors.current_cycle_used}</p>}
      </div>

      {requestError && <div className="request-error" role="alert">{requestError}</div>}

      <button className="primary-button" type="submit" disabled={loading}>
        {loading ? <><span className="button-spinner" aria-hidden="true" />Planning trip…</> : <>Plan trip <span aria-hidden="true">→</span></>}
      </button>
      <p className="form-footnote">All trip locations and cycle hours are required.</p>
    </form>
  )
}

export default TripForm
