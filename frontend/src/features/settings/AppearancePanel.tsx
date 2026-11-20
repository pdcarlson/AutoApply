/** Settings panel for choosing the light, dark or device theme. */
import { useTheme, type ThemeChoice } from '@/app/providers/theme';
import { Panel, PanelHead } from '@/components/ui/Panel';
import { Segmented } from '@/components/ui/Segmented';

const THEMES: { value: ThemeChoice; label: string }[] = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
  { value: 'system', label: 'Match my device' },
];

/** A segmented theme picker. */
export function AppearancePanel() {
  const { choice, setChoice } = useTheme();
  return (
    <Panel aria-labelledby="appearance-title">
      <PanelHead>
        <h2 className="h3" id="appearance-title">
          Appearance
        </h2>
      </PanelHead>
      <Segmented
        labelledBy="appearance-title"
        options={THEMES}
        value={choice}
        onChange={setChoice}
      />
      <span className="tiny muted">
        Your choice is kept across screens and visits on this device.
      </span>
    </Panel>
  );
}
