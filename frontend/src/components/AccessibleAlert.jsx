/**
 * Accessible alert component for displaying errors and success messages.
 * Implements ARIA live regions for screen reader announcements.
 *
 * TODO: Production enhancements:
 * - Add animation for alert appearance/disappearance
 * - Implement auto-dismiss with configurable timeout
 * - Add different alert types (info, warning, error, success)
 * - Support dismissible alerts
 */

export function AccessibleAlert({
  type = 'error', // 'error', 'success', 'warning', 'info'
  title,
  message,
  items = [],
  id,
}) {
  const typeStyles = {
    error: {
      container: 'bg-red-50 border-red-200',
      icon: 'text-red-600',
      title: 'text-red-800',
      text: 'text-red-700',
      iconPath: 'M6 18L18 6M6 6l12 12',
    },
    success: {
      container: 'bg-green-50 border-green-200',
      icon: 'text-green-600',
      title: 'text-green-800',
      text: 'text-green-700',
      iconPath: 'M5 13l4 4L19 7',
    },
    warning: {
      container: 'bg-yellow-50 border-yellow-200',
      icon: 'text-yellow-600',
      title: 'text-yellow-800',
      text: 'text-yellow-700',
      iconPath:
        'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
    },
    info: {
      container: 'bg-blue-50 border-blue-200',
      icon: 'text-blue-600',
      title: 'text-blue-800',
      text: 'text-blue-700',
      iconPath: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
    },
  };

  const styles = typeStyles[type] || typeStyles.error;

  return (
    <div
      id={id}
      role="alert"
      aria-live={type === 'error' ? 'assertive' : 'polite'}
      aria-atomic="true"
      className={`border rounded-lg p-4 ${styles.container}`}
    >
      <div className="flex items-start">
        <div className={`flex-shrink-0 ${styles.icon}`}>
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d={styles.iconPath}
            />
          </svg>
        </div>
        <div className="ml-3 flex-1">
          {title && <h3 className={`text-sm font-medium ${styles.title} mb-1`}>{title}</h3>}
          {message && <p className={`text-sm ${styles.text}`}>{message}</p>}
          {items && items.length > 0 && (
            <ul className={`mt-2 list-disc list-inside text-sm ${styles.text}`}>
              {items.map(item => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
