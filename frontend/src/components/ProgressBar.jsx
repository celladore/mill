/**
 * Accessible progress bar component for showing upload/conversion progress.
 *
 * Supports determinate progress and honest indeterminate feedback when the
 * server cannot report meaningful completion percentages.
 */

export function ProgressBar({
  value = 0, // 0-100
  max = 100,
  label = 'Progress',
  showPercentage = true,
  ariaLabel,
  indeterminate = false,
  detail,
}) {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100);

  return (
    <div className="progress-shell">
      <div className="progress-heading">
        <span>{label}</span>
        {showPercentage && !indeterminate && (
          <span aria-hidden="true">{Math.round(percentage)}%</span>
        )}
      </div>
      <div className="progress-track">
        <div
          role="progressbar"
          aria-valuenow={indeterminate ? undefined : value}
          aria-valuemin={indeterminate ? undefined : 0}
          aria-valuemax={indeterminate ? undefined : max}
          aria-valuetext={indeterminate ? 'In progress' : undefined}
          aria-label={ariaLabel || label}
          className={`progress-fill ${indeterminate ? 'is-indeterminate' : ''}`}
          style={indeterminate ? undefined : { width: `${percentage}%` }}
        />
      </div>
      {detail && <p className="progress-detail">{detail}</p>}
    </div>
  );
}
