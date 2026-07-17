import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { CaseList } from "../../components/cases/case-list";
import { CreateCaseGate } from "../../components/cases/create-case-gate";
import { CreateCaseForm } from "../../components/cases/create-case-form";
import { AppShell } from "../../components/shell/app-shell";
import type { CreditCaseDto } from "../../lib/api/contracts";

const cases: CreditCaseDto[] = [
  {
    id: "case-allowed",
    version: 2,
    assignedOfficerId: "officer-synthetic",
    requestedAmount: "5000000000",
    purpose: "Bổ sung vốn lưu động",
    workflowState: "INTAKE",
    updatedAt: "2026-07-17T08:00:00Z",
    capabilities: {
      canUpload: true,
      canConfirm: true,
      canCompleteIntake: false,
    },
  },
  {
    id: "case-read-only",
    version: 1,
    assignedOfficerId: "officer-synthetic",
    requestedAmount: null,
    purpose: "Mua nguyên vật liệu",
    workflowState: null,
    updatedAt: null,
    capabilities: {
      canUpload: false,
      canConfirm: false,
      canCompleteIntake: false,
    },
  },
];

describe("CaseList", () => {
  it("loads assigned cases and exposes upload only from server capabilities", async () => {
    const api = {
      listCases: vi.fn().mockResolvedValue({
        items: cases,
        nextCursor: null,
        capabilities: { canCreateCase: false },
      }),
    };

    render(<CaseList api={api} />);

    expect(screen.getByLabelText("Đang tải danh sách hồ sơ")).toBeVisible();
    expect(await screen.findByText("Bổ sung vốn lưu động")).toBeVisible();
    expect(screen.getByText("Mua nguyên vật liệu")).toBeVisible();
    expect(screen.getByText("Đang tiếp nhận")).toBeVisible();
    expect(screen.queryByText("INTAKE")).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Tiếp nhận tài liệu — Bổ sung vốn lưu động" }),
    ).toHaveAttribute("href", "/ho-so/case-allowed/tiep-nhan");
    expect(
      screen.queryByRole("link", { name: "Tiếp nhận tài liệu — Mua nguyên vật liệu" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Không có quyền tải tài liệu")).toBeVisible();
    expect(screen.queryByRole("link", { name: "Tạo hồ sơ" })).not.toBeInTheDocument();
  });

  it("fails closed on case creation when the collection capability is false", async () => {
    const api = {
      listCases: vi.fn().mockResolvedValue({
        items: [],
        nextCursor: null,
        capabilities: { canCreateCase: false },
      }),
    };

    render(<CaseList api={api} />);

    expect(await screen.findByText("Chưa có hồ sơ được phân công")).toBeVisible();
    expect(screen.queryByText(/Công ty/)).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Tạo hồ sơ" })).not.toBeInTheDocument();
    expect(screen.getByText("Bạn không có quyền tạo hồ sơ minh họa.")).toBeVisible();
  });

  it("shows synthetic case creation only from the collection capability", async () => {
    const api = {
      listCases: vi.fn().mockResolvedValue({
        items: [],
        nextCursor: null,
        capabilities: { canCreateCase: true },
      }),
    };

    render(<CaseList api={api} />);

    expect(await screen.findByRole("link", { name: "Tạo hồ sơ" })).toHaveAttribute(
      "href",
      "/ho-so/tao-moi",
    );
    expect(screen.getByText(/dữ liệu tổng hợp dùng cho trình diễn/i)).toBeVisible();
  });

  it("lets the officer retry a failed case request", async () => {
    const api = {
      listCases: vi
        .fn()
        .mockRejectedValueOnce(new Error("offline"))
        .mockResolvedValueOnce({
          items: cases.slice(0, 1),
          nextCursor: null,
          capabilities: { canCreateCase: false },
        }),
    };

    render(<CaseList api={api} />);

    fireEvent.click(await screen.findByRole("button", { name: "Thử tải lại" }));

    expect(await screen.findByText("Bổ sung vốn lưu động")).toBeVisible();
    expect(api.listCases).toHaveBeenCalledTimes(2);
  });

  it("labels an unknown workflow state as unknown", async () => {
    const api = {
      listCases: vi.fn().mockResolvedValue({
        items: [{ ...cases[0], workflowState: "UNRECOGNIZED_STATE" }],
        nextCursor: null,
        capabilities: { canCreateCase: false },
      }),
    };

    render(<CaseList api={api} />);

    expect(await screen.findByText("Trạng thái không xác định")).toBeVisible();
    expect(screen.queryByText("Đang xử lý")).not.toBeInTheDocument();
  });
});

describe("CreateCaseForm", () => {
  it("submits only the financing request fields supplied by the officer", async () => {
    const api = {
      createCase: vi.fn().mockResolvedValue(cases[0]),
    };

    render(<CreateCaseForm api={api} canCreateCase />);
    fireEvent.change(screen.getByLabelText("Số tiền đề nghị"), {
      target: { value: "5000000000" },
    });
    fireEvent.change(screen.getByLabelText("Mục đích vay vốn"), {
      target: { value: "Bổ sung vốn lưu động" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Tạo hồ sơ" }));

    await waitFor(() =>
      expect(api.createCase).toHaveBeenCalledWith({
        requestedAmount: "5000000000",
        purpose: "Bổ sung vốn lưu động",
      }),
    );
    expect(
      await screen.findByRole("link", { name: "Mở hồ sơ vừa tạo" }),
    ).toHaveAttribute("href", "/ho-so/case-allowed/tiep-nhan");
  });

  it("does not submit missing financing details", async () => {
    const api = { createCase: vi.fn() };

    render(<CreateCaseForm api={api} canCreateCase />);
    fireEvent.click(screen.getByRole("button", { name: "Tạo hồ sơ" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Có 2 trường cần kiểm tra.");
    expect(await screen.findByText("Nhập số tiền đề nghị.")).toBeVisible();
    expect(screen.getByText("Nhập mục đích vay vốn.")).toBeVisible();
    expect(screen.getByLabelText("Số tiền đề nghị")).toHaveFocus();
    expect(api.createCase).not.toHaveBeenCalled();
  });

  it("does not render a form without collection create authority", () => {
    const api = { createCase: vi.fn() };

    render(<CreateCaseForm api={api} canCreateCase={false} />);

    expect(screen.queryByRole("button", { name: "Tạo hồ sơ" })).not.toBeInTheDocument();
    expect(screen.getByText("Bạn không có quyền tạo hồ sơ minh họa.")).toBeVisible();
  });
});

describe("CreateCaseGate", () => {
  it("fails closed when direct navigation has no create capability", async () => {
    const api = {
      listCases: vi.fn().mockResolvedValue({
        items: [],
        nextCursor: null,
        capabilities: { canCreateCase: false },
      }),
      createCase: vi.fn(),
    };

    render(<CreateCaseGate api={api} />);

    expect(await screen.findByText("Bạn không có quyền tạo hồ sơ minh họa.")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Tạo hồ sơ" })).not.toBeInTheDocument();
  });
});

describe("AppShell", () => {
  it("does not expose an unconditional create-case action", () => {
    render(<AppShell><p>Nội dung tổng hợp</p></AppShell>);

    expect(screen.queryByRole("link", { name: "Tạo hồ sơ" })).not.toBeInTheDocument();
  });
});
