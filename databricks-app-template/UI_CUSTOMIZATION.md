# UI Customization Quick Guide

This checklist captures all UI branding and color changes discussed so far.
Use it for quick future updates.

## 1) Header title / workflow label

Preferred (no code change):
- Set this env var before building the UI:
  - NEXT_PUBLIC_NAT_WORKFLOW="Specialized Nutrition Quality Control Agent"

Fallback (code):
- constants/index.js
  - APPLICATION_NAME
  - APPLICATION_UI_NAME
  - SESSION_COOKIE_NAME (optional rename for rebrand)

## 2) Greeting and input placeholder

- components/Chat/ChatHeader.tsx
  - "How can I assist you today?"
- components/Chat/ChatInput.tsx
  - `Unlock ${workflow} knowledge and expertise`

## 3) Favicon and bot avatar

Option A (quickest):
- Replace NeMo-Agent-Toolkit-UI/public/nvidia.jpg with your icon (same filename).

Option B (rename file):
- Add new file, e.g. public/snqc.png, then update:
  - components/Chat/ChatMessage.tsx (BotAvatar src)
  - components/Chat/ChatLoader.tsx (BotAvatar src)
  - components/Avatar/BotAvatar.tsx (fallback src)
  - pages/api/home/home.tsx (favicon link)
  - pages/database-updates.tsx (favicon link)

## 4) Intermediate Steps color

- components/Markdown/CustomSummary.tsx
  - hover:text-[#76b900]
  - IconTool/IconCpu/IconLoader text-[#76b900]
- components/Markdown/CustomDetails.tsx
  - hover:text-[#76b900] text-[#76b900]
  - loading bar bg-[#76b900]

## 5) Global brand color (green to blue)

Replace #76b900 and #91c438 with your blue in these files:
- components/Chat/ChatHeader.tsx
- components/Chat/ChatInput.tsx
- components/Chat/ChatMessage.tsx
- components/Chat/ChatLoader.tsx
- components/Markdown/CustomSummary.tsx
- components/Markdown/CustomDetails.tsx
- components/Markdown/CustomComponents.tsx
- components/Markdown/Chart.tsx
- components/Settings/SettingDialog.tsx
- components/Avatar/UserAvatar.tsx
- components/Chat/DataStreamControls.tsx
- components/MCP/MCPModal.tsx
- pages/database-updates.tsx
- __tests__/components/InteractionModal.test.tsx

## 6) Rebuild and cache

- Rebuild the UI after changes (npm run build).
- Hard-refresh the browser to clear cached favicon/CSS.
