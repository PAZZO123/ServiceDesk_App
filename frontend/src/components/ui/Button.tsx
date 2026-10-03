import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link, type LinkProps } from "react-router";
import { Icon, type IconName } from "./Icon";
import { Spinner } from "./Feedback";
import { buttonClass, type Size, type Variant } from "./button-class";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  icon?: IconName;
  iconRight?: IconName;
  loading?: boolean;
  children?: ReactNode;
};

export function Button({
  variant = "primary",
  size = "md",
  icon,
  iconRight,
  loading = false,
  className = "",
  children,
  disabled,
  type = "button",
  ...rest
}: ButtonProps) {
  const iconSize = size === "lg" ? "size-5" : "size-4";
  return (
    <button
      type={type}
      className={buttonClass(variant, size, className)}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <Spinner className={iconSize} /> : icon && <Icon name={icon} className={iconSize} />}
      {children}
      {iconRight && !loading && <Icon name={iconRight} className={iconSize} />}
    </button>
  );
}

type ButtonLinkProps = LinkProps & {
  variant?: Variant;
  size?: Size;
  icon?: IconName;
  iconRight?: IconName;
};

export function ButtonLink({
  variant = "primary",
  size = "md",
  icon,
  iconRight,
  className = "",
  children,
  ...rest
}: ButtonLinkProps) {
  const iconSize = size === "lg" ? "size-5" : "size-4";
  return (
    <Link className={buttonClass(variant, size, className)} {...rest}>
      {icon && <Icon name={icon} className={iconSize} />}
      {children}
      {iconRight && <Icon name={iconRight} className={iconSize} />}
    </Link>
  );
}
