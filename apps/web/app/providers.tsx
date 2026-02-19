"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PropsWithChildren, useState } from "react";

export function Providers({ children }: PropsWithChildren) {
  const [client] = useState(() =>
    new QueryClient({
      defaultOptions: {
        queries: { refetchOnWindowFocus: false, staleTime: 15_000 },
      },
    }),
  );

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
