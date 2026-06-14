import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { makeCall } from "@/test-utils";
import { CallsTable } from "../CallsTable";

test("shows the empty state but keeps the sortable headers mounted", () => {
  render(<CallsTable calls={[]} onRowClick={() => {}} />);
  expect(screen.getByText("No calls found")).toBeTruthy();
  expect(screen.getByText("Duration")).toBeTruthy(); // headers persist so sort stays usable
});

test("renders a badge per status and formats durations", () => {
  render(
    <CallsTable
      calls={[
        makeCall({ id: "1", status: "in_progress", duration_seconds: null }),
        makeCall({ id: "2", status: "success", duration_seconds: 125 }),
        makeCall({ id: "3", status: "failed", duration_seconds: 45 }),
      ]}
      onRowClick={() => {}}
    />,
  );
  expect(screen.getByText("In Progress")).toBeTruthy();
  expect(screen.getByText("Success")).toBeTruthy();
  expect(screen.getByText("Failed")).toBeTruthy();
  expect(screen.getByText("2m 5s")).toBeTruthy(); // 125s
  expect(screen.getByText("45s")).toBeTruthy(); // 45s
});

test("renders the label badge and selects the call on row click", () => {
  const onRowClick = vi.fn();
  const labeled = makeCall({ id: "a", label: "Support", caller_name: "García" });
  const unlabeled = makeCall({ id: "b", label: null, caller_name: "Owens" });
  render(<CallsTable calls={[labeled, unlabeled]} onRowClick={onRowClick} />);

  expect(screen.getByText("Support")).toBeTruthy();
  fireEvent.click(screen.getByText("García"));
  expect(onRowClick).toHaveBeenCalledWith(labeled);
});
