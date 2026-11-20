/** Drag-and-drop area and file button for uploading a resume. */
import { useState, type ChangeEvent, type DragEvent } from 'react';
import { buttonClass } from '@/components/ui/classNames';
import { Icon } from '@/components/ui/Icon';
import { Spinner } from '@/components/ui/Spinner';
import { cx } from '@/lib/cx';
import { RESUME_ACCEPT } from '@/lib/resumeFile';
import styles from './ResumeDropZone.module.css';

interface ResumeDropZoneProps {
  onFile: (file: File | undefined) => void;
  uploading: boolean;
}

/** Accepts a dropped or chosen resume file and hands it to `onFile`. */
export function ResumeDropZone({ onFile, uploading }: ResumeDropZoneProps) {
  const [isDragging, setIsDragging] = useState(false);

  const handleDragOver = (event: DragEvent) => {
    event.preventDefault();
    setIsDragging(true);
  };
  const handleDrop = (event: DragEvent) => {
    event.preventDefault();
    setIsDragging(false);
    onFile(event.dataTransfer.files[0]);
  };
  const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    onFile(event.target.files?.[0]);
    // Clear the input so picking the same file again still fires a change.
    event.target.value = '';
  };

  return (
    <div
      className={cx(styles.dropZone, isDragging && styles.dragging)}
      onDragOver={handleDragOver}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
    >
      <span className={styles.dropIcon}>
        <Icon name="upload" size={26} stroke={1.75} />
      </span>
      <span className={styles.dropTitle}>Drop your resume here</span>
      <span className="small muted">PDF or DOCX, up to 5 MB</span>
      {uploading ? (
        <span className={styles.uploading}>
          <Spinner /> Uploading…
        </span>
      ) : (
        <label className={buttonClass({ variant: 'primary' })} htmlFor="resume-file">
          Choose a file
        </label>
      )}
      <input
        id="resume-file"
        type="file"
        accept={RESUME_ACCEPT}
        hidden
        onChange={handleInputChange}
      />
    </div>
  );
}
