/**
 * Accessible progress bar component for showing upload/conversion progress.
 *
 * TODO: Production enhancements:
 * - Add animated progress indication
 * - Support indeterminate progress (when percentage unknown)
 * - Add time remaining estimation
 * - Implement progress cancellation
 */

export function ProgressBar({
  value = 0, // 0-100
  max = 100,
  label = 'Progress',
  showPercentage = true,
  ariaLabel,
}) {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100);

  return (
    <div className="w-full">
      <div className="flex justify-between items-center mb-2">
        <label htmlFor="progress-bar" className="text-sm font-medium text-gray-700">
          {label}
        </label>
        {showPercentage && (
          <span className="text-sm text-gray-600" aria-hidden="true">
            {Math.round(percentage)}%
          </span>
        )}
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2.5">
        <div
          id="progress-bar"
          role="progressbar"
          aria-valuenow={value}
          aria-valuemin={0}
          aria-valuemax={max}
          aria-label={ariaLabel || label}
          className="bg-blue-600 h-2.5 rounded-full transition-all duration-300 ease-out"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
