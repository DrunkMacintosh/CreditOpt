import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { CaseList } from "../../components/cases/case-list";
import { CreateCaseForm } from "../../components/cases/create-case-form";
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
    const api = { listCases: vi.fn().mockResolvedValue(cases) };

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
  });

  it("shows an explicit empty state without inventing a customer", async () => {
    const api = { listCases: vi.fn().mockResolvedValue([]) };

    render(<CaseList api={api} />);

    expect(await screen.findByText("Chưa có hồ sơ được phân công")).toBeVisible();
    expect(screen.queryByText(/Công ty/)).not.toBeInTheDocument();
  });

  it("lets the officer retry a failed case request", async () => {
    const api = {
      listCases: vi
        .fn()
        .mockRejectedValueOnce(new Error("offline"))
        .mockResolvedValueOnce(cases.slice(0, 1)),
    };

    render(<CaseList api={api} />);

    fireEvent.click(await screen.findByRole("button", { name: "Thử tải lại" }));

    expect(await screen.findByText("Bổ sung vốn lưu động")).toBeVisible();
    expect(api.listCases).toHaveBeenCalledTimes(2);
  });
});

describe("CreateCaseForm", () => {
  it("submits only the financing request fields supplied by the officer", async () => {
    const api = {
      createCase: vi.fn().mockResolvedValue(cases[0]),
    };

    render(<CreateCaseForm api={api} />);
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

    render(<CreateCaseForm api={api} />);
    fireEvent.click(screen.getByRole("button", { name: "Tạo hồ sơ" }));

    expect(await screen.findByText("Nhập số tiền đề nghị.")).toBeVisible();
    expect(screen.getByText("Nhập mục đích vay vốn.")).toBeVisible();
    expect(api.createCase).not.toHaveBeenCalled();
  });
});
