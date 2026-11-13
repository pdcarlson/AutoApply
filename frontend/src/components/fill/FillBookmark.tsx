import { useEffect, useRef } from 'react';
import { buttonClass } from '@/components/ui/classNames';
import { FILL_BOOKMARK } from '@/lib/fillBookmark';

/**
 * A link the user drags to their bookmarks bar. React won't render a `javascript:` href, so it's
 * set on the element directly; clicking it here does nothing.
 */
export function FillBookmark() {
  const link = useRef<HTMLAnchorElement>(null);
  useEffect(() => {
    link.current?.setAttribute('href', FILL_BOOKMARK);
  }, []);
  return (
    <a
      ref={link}
      className={buttonClass({ size: 'sm' })}
      onClick={(event) => event.preventDefault()}
      title="Drag me to your bookmarks bar"
    >
      Fill with AutoApply
    </a>
  );
}
