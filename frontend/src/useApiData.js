import { useEffect, useState } from "react";

// Load data from the API. If the API is down or has nothing yet, show the
// sample data instead so the screen is never blank while we're building.
export default function useApiData(fetcher, fallback) {
  const [data, setData] = useState(fallback);
  const [usingSample, setUsingSample] = useState(true);

  async function reload() {
    try {
      const result = await fetcher();
      const empty = Array.isArray(result) && result.length === 0;
      if (!empty) {
        setData(result);
        setUsingSample(false);
      }
    } catch {
      // API offline: keep sample data
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { data, setData, usingSample, reload };
}
