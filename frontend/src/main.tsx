import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { queryClient } from "./lib/api";
import { ThemeProvider } from "./lib/theme";
import { AssetProvider } from "./lib/assets";
import { EditionRegistryProvider } from "./themes/olympicThemeEngine";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AssetProvider>
          <EditionRegistryProvider>
            <BrowserRouter>
              <App />
            </BrowserRouter>
          </EditionRegistryProvider>
        </AssetProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
