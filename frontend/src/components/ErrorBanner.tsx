import { InlineAlert } from "./ui/InlineAlert";

interface ErrorBannerProps {
  code?: string;
  message: string;
  onRetry?: () => void;
}

export function ErrorBanner({ code, message, onRetry }: ErrorBannerProps) {
  return <InlineAlert tone="error" code={code} message={message} onRetry={onRetry} />;
}
