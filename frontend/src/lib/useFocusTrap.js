import { useEffect } from "react";

// Selector for elements that can receive keyboard focus inside a dialog.
const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Trap keyboard focus inside a dialog while it is open, and restore focus to
 * whatever was focused before it opened once it closes.
 *
 * - On open: moves focus into the container (its first focusable element, or the
 *   container itself if it has none yet — e.g. content is still loading).
 * - While open: Tab / Shift+Tab cycle between the first and last focusable
 *   elements instead of escaping to the page behind the dialog.
 * - On close/unmount: restores focus to the previously-focused element.
 *
 * Escape-to-close stays the caller's responsibility (each dialog already wires
 * its own Escape handler).
 *
 * @param {{current: HTMLElement|null}} ref  ref on the dialog container
 * @param {boolean} isOpen
 */
export function useFocusTrap(ref, isOpen) {
  useEffect(() => {
    if (!isOpen) return;
    const node = ref.current;
    if (!node) return;

    const previouslyFocused =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;

    // Move focus into the dialog. Prefer the first focusable element; fall back
    // to the container itself (made programmatically focusable) so focus never
    // lingers on the page behind the dialog while its content loads.
    const focusFirst = () => {
      const focusables = node.querySelectorAll(FOCUSABLE);
      if (focusables.length > 0) {
        focusables[0].focus();
      } else {
        if (!node.hasAttribute("tabindex")) node.setAttribute("tabindex", "-1");
        node.focus();
      }
    };
    focusFirst();

    const onKeyDown = (e) => {
      if (e.key !== "Tab") return;
      const focusables = Array.from(node.querySelectorAll(FOCUSABLE)).filter(
        (el) => el.offsetParent !== null || el === document.activeElement
      );
      if (focusables.length === 0) {
        // Nothing focusable yet — keep focus on the container.
        e.preventDefault();
        node.focus();
        return;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;
      if (e.shiftKey) {
        if (active === first || !node.contains(active)) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (active === last || !node.contains(active)) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    node.addEventListener("keydown", onKeyDown);
    return () => {
      node.removeEventListener("keydown", onKeyDown);
      if (previouslyFocused && document.contains(previouslyFocused)) {
        previouslyFocused.focus();
      }
    };
  }, [ref, isOpen]);
}
