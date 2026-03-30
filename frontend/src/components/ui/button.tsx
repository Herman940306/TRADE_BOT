import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 disabled:pointer-events-none disabled:opacity-50 cursor-pointer",
  {
    variants: {
      variant: {
        default: "bg-accent/10 text-accent border border-accent/30 hover:bg-accent/20 hover:shadow-[0_0_15px_rgba(0,255,225,0.2)]",
        primary: "bg-accent text-sovereign-bg hover:bg-accent-dim hover:shadow-[0_0_20px_rgba(0,255,225,0.3)]",
        danger: "bg-danger/10 text-danger border border-danger/30 hover:bg-danger/20 hover:shadow-[0_0_15px_rgba(255,77,77,0.2)]",
        dangerSolid: "bg-danger text-white hover:bg-danger-dim",
        ghost: "text-sovereign-muted hover:text-sovereign-text hover:bg-sovereign-surface",
        outline: "border border-sovereign-border text-sovereign-text hover:bg-sovereign-surface",
        success: "bg-success/10 text-success border border-success/30 hover:bg-success/20",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 px-3 text-xs",
        lg: "h-11 px-8 text-base",
        xl: "h-14 px-10 text-lg",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
