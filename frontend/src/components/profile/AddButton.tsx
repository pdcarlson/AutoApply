/** The "+ Add ..." button under each profile list editor. */
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import styles from './AddButton.module.css';

interface AddButtonProps {
  onClick: () => void;
  children: string;
}

/** A small ghost button with a plus icon that adds a row to a list. */
export function AddButton({ onClick, children }: AddButtonProps) {
  return (
    <Button variant="ghost" size="sm" className={styles.add} onClick={onClick}>
      <Icon name="plus" size={16} stroke={2} />
      {children}
    </Button>
  );
}
