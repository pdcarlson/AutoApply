/** Scrolls the Profile page to the section named in the URL hash. */
import { useEffect } from 'react';
import { useLocation } from 'react-router';
import { sectionElementId } from './sections';

/** Scrolls to `#education` and the like whenever the hash changes. */
export function useScrollToHashSection() {
  const { hash } = useLocation();
  useEffect(() => {
    const key = hash.slice(1);
    if (key) document.getElementById(sectionElementId(key))?.scrollIntoView({ block: 'start' });
  }, [hash]);
}
