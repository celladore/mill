/**
 * Accessible file upload component with ARIA labels, keyboard navigation,
 * and screen reader support.
 *
 * TODO: Production enhancements:
 * - Add file preview before upload
 * - Implement drag-and-drop visual feedback
 * - Add file size validation with clear error messages
 * - Support multiple file selection
 * - Add file type validation with clear feedback
 */

import { useRef, useState } from 'react';

export function AccessibleFileUpload({
  accept,
  maxSize,
  onFileSelect,
  label = 'Choose file',
  description = '',
  error = null,
  disabled = false,
  dragActive = false,
  onDragEnter,
  onDragLeave,
  onDragOver,
  onDrop,
}) {
  const fileInputRef = useRef(null);
  const [focused, setFocused] = useState(false);

  const handleKeyDown = e => {
    if (disabled) return;

    // Space or Enter to open file dialog
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      fileInputRef.current?.click();
    }
  };

  const handleFileChange = e => {
    const file = e.target.files?.[0];
    if (file) {
      // Validate file size
      if (maxSize && file.size > maxSize) {
        const maxSizeMB = (maxSize / (1024 * 1024)).toFixed(0);
        onFileSelect(null, `File size exceeds ${maxSizeMB}MB limit`);
        return;
      }
      onFileSelect(file, null);
    }
  };

  const handleDropInternal = e => {
    e.preventDefault();
    e.stopPropagation();
    if (onDrop) {
      onDrop(e);
    }
    const file = e.dataTransfer.files?.[0];
    if (file) {
      if (maxSize && file.size > maxSize) {
        const maxSizeMB = (maxSize / (1024 * 1024)).toFixed(0);
        onFileSelect(null, `File size exceeds ${maxSizeMB}MB limit`);
        return;
      }
      onFileSelect(file, null);
    }
  };

  return (
    <div className="file-upload-container">
      <label htmlFor="file-input" className="sr-only">
        {label}
        {description && ` - ${description}`}
      </label>

      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-label={label}
        aria-describedby={description ? 'file-upload-description' : undefined}
        aria-disabled={disabled}
        aria-invalid={error ? 'true' : undefined}
        onKeyDown={handleKeyDown}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        className={`
          border-2 border-dashed rounded-lg p-8 text-center transition-all duration-200
          ${dragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300'}
          ${focused ? 'ring-2 ring-blue-500 ring-offset-2' : ''}
          ${disabled ? 'opacity-50 cursor-not-allowed' : 'hover:border-gray-400 cursor-pointer'}
          ${error ? 'border-red-500 bg-red-50' : ''}
        `}
        onDragEnter={onDragEnter}
        onDragLeave={onDragLeave}
        onDragOver={onDragOver}
        onDrop={handleDropInternal}
        onClick={() => !disabled && fileInputRef.current?.click()}
      >
        <div className="mb-4" aria-hidden="true">
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
            stroke="currentColor"
            fill="none"
            viewBox="0 0 48 48"
          >
            <path
              d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>

        <p className="text-lg text-gray-600 mb-2">{label}</p>

        {description && (
          <p id="file-upload-description" className="text-sm text-gray-500 mb-4">
            {description}
          </p>
        )}

        <input
          id="file-input"
          ref={fileInputRef}
          type="file"
          className="sr-only"
          accept={accept}
          onChange={handleFileChange}
          disabled={disabled}
          aria-describedby={error ? 'file-upload-error' : undefined}
        />
      </div>

      {error && (
        <div
          id="file-upload-error"
          role="alert"
          aria-live="polite"
          className="mt-2 text-sm text-red-600"
        >
          {error}
        </div>
      )}
    </div>
  );
}
