import { ApiError } from "../api/client";

type FieldError = { field: string; message: string };

// The backend's 422 body lists every bad field (exceptions.py). Turn the
// envelope into one readable sentence for a form.
export function errorMessage(error: unknown, fallback = "Something went wrong. Please try again."): string {
  if (error instanceof ApiError) {
    if (error.code === "validation_error" && error.details && typeof error.details === "object") {
      const fields = (error.details as { fields?: FieldError[] }).fields;
      if (Array.isArray(fields) && fields.length > 0) {
        return fields.map((f) => `${f.field.replace(/_/g, " ")}: ${f.message}`).join(". ");
      }
    }
    if (error.status === 0 || error.status >= 500) return fallback;
    return error.message;
  }
  if (error instanceof TypeError) return "Cannot reach the server. Check your connection.";
  return fallback;
}

export function isStatus(error: unknown, ...statuses: number[]): boolean {
  return error instanceof ApiError && statuses.includes(error.status);
}

export function errorCode(error: unknown): string | null {
  return error instanceof ApiError ? error.code : null;
}
