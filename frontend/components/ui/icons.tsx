import { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

const icon =
  (path: string) =>
  ({ size = 16, ...props }: IconProps) =>
    (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.75}
        strokeLinecap="round"
        strokeLinejoin="round"
        {...props}
      >
        <path d={path} />
      </svg>
    );

export const LayoutDashboard = icon(
  "M3 3h7v9H3zm11 0h7v5h-7zm0 9h7v9h-7zM3 16h7v5H3z"
);
export const Briefcase = icon(
  "M20 7H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2zm-9-4h2a2 2 0 0 1 2 2v2H9V5a2 2 0 0 1 2-2z"
);
export const ClipboardList = icon(
  "M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2m-6 9h6m-6 4h4"
);
export const Zap = icon("M13 2 3 14h9l-1 8 10-12h-9l1-8z");
export const ScanSearch = icon(
  "M3 7V5a2 2 0 0 1 2-2h2m10 0h2a2 2 0 0 1 2 2v2m0 10v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2m5-5a3 3 0 1 0 6 0 3 3 0 0 0-6 0zm4.24 2.76 2 2"
);
export const History = icon(
  "M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8m0-5v5h5m4-1v5l4 2"
);
export const BarChart3 = icon("M3 3v18h18M18 9v9M13 5v13M8 13v5");
export const Settings = icon(
  "M12 20a8 8 0 1 0 0-16 8 8 0 0 0 0 16zm0-5a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"
);
export const ChevronLeft = icon("M15 18l-6-6 6-6");
export const ChevronRight = icon("M9 18l6-6-6-6");
export const LogOut = icon(
  "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4m7 14 5-5-5-5m5 5H9"
);
