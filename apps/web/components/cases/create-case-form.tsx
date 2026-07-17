"use client";

import Link from "next/link";
import React, { type FormEvent, useState } from "react";

import { creditOpsApi, getVietnameseApiError } from "../../lib/api/client";
import type { CreditCaseDto } from "../../lib/api/contracts";

interface CreateCaseFormProps {
  api?: Pick<typeof creditOpsApi, "createCase">;
}

interface FormErrors {
  requestedAmount?: string;
  purpose?: string;
}

export function CreateCaseForm({ api = creditOpsApi }: CreateCaseFormProps) {
  const [requestedAmount, setRequestedAmount] = useState("");
  const [purpose, setPurpose] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [createdCase, setCreatedCase] = useState<CreditCaseDto | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors: FormErrors = {};
    const amount = requestedAmount.trim();
    const financingPurpose = purpose.trim();

    if (!amount) nextErrors.requestedAmount = "Nhập số tiền đề nghị.";
    else if (!/^\d+$/.test(amount) || BigInt(amount) <= BigInt(0)) {
      nextErrors.requestedAmount = "Số tiền đề nghị phải là số nguyên dương.";
    }
    if (!financingPurpose) nextErrors.purpose = "Nhập mục đích vay vốn.";
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    setSubmitting(true);
    setRequestError(null);
    try {
      setCreatedCase(
        await api.createCase({ requestedAmount: amount, purpose: financingPurpose }),
      );
    } catch (error) {
      setRequestError(getVietnameseApiError(error));
    } finally {
      setSubmitting(false);
    }
  }

  if (createdCase) {
    return (
      <div className="state-panel" role="status">
        <h2>Đã tạo hồ sơ</h2>
        <p>Thông tin đã được ghi nhận. Tài liệu chỉ được đăng ký sau khi kho lưu trữ xác minh.</p>
        <Link
          className="button button-primary"
          href={`/ho-so/${encodeURIComponent(createdCase.id)}/tiep-nhan`}
        >
          Mở hồ sơ vừa tạo
        </Link>
      </div>
    );
  }

  return (
    <form className="case-form" noValidate onSubmit={submit}>
      <div className="field-group">
        <label htmlFor="requested-amount">Số tiền đề nghị</label>
        <div className="input-suffix">
          <input
            aria-describedby={errors.requestedAmount ? "requested-amount-error" : "requested-amount-help"}
            aria-invalid={Boolean(errors.requestedAmount)}
            autoComplete="off"
            id="requested-amount"
            inputMode="numeric"
            onChange={(event) => setRequestedAmount(event.target.value)}
            placeholder="Ví dụ: 5000000000"
            value={requestedAmount}
          />
          <span>VND</span>
        </div>
        <p className="field-help" id="requested-amount-help">
          Nhập số nguyên, không dùng dấu phân cách.
        </p>
        {errors.requestedAmount ? (
          <p className="field-error" id="requested-amount-error">
            {errors.requestedAmount}
          </p>
        ) : null}
      </div>

      <div className="field-group">
        <label htmlFor="financing-purpose">Mục đích vay vốn</label>
        <textarea
          aria-describedby={errors.purpose ? "purpose-error" : "purpose-help"}
          aria-invalid={Boolean(errors.purpose)}
          id="financing-purpose"
          maxLength={500}
          onChange={(event) => setPurpose(event.target.value)}
          placeholder="Mô tả nhu cầu vốn lưu động do cán bộ ghi nhận"
          rows={5}
          value={purpose}
        />
        <p className="field-help" id="purpose-help">
          Không nhập thông tin khách hàng không cần thiết cho nhu cầu cấp vốn.
        </p>
        {errors.purpose ? (
          <p className="field-error" id="purpose-error">
            {errors.purpose}
          </p>
        ) : null}
      </div>

      {requestError ? <p className="form-alert" role="alert">{requestError}</p> : null}
      <div className="form-actions">
        <button className="button button-primary" disabled={submitting} type="submit">
          {submitting ? "Đang tạo hồ sơ…" : "Tạo hồ sơ"}
        </button>
        <Link className="button button-quiet" href="/ho-so">
          Hủy
        </Link>
      </div>
    </form>
  );
}
