import React, { useEffect } from "react";
import { PanelLeftClose, X } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useMediaQuery } from "@/hooks/useMediaQuery";

interface SidebarProps {
  isOpen: boolean;
  toggle: () => void;
  children?: React.ReactNode;
}

const Sidebar: React.FC<SidebarProps> = ({ isOpen, toggle, children }) => {
  const isDesktop = useMediaQuery("(min-width: 768px)");
  
  // Close sidebar on escape key press (mobile only)
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen && !isDesktop) toggle();
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [isOpen, toggle, isDesktop]);

  // Desktop: always visible, sticky
  // Mobile: slide-in drawer
  const sidebarVariants = {
    desktop: { x: 0, width: 256 },
    mobileOpen: { x: 0, width: 256 },
    mobileClosed: { x: -256, width: 0 },
  };

  const currentVariant = isDesktop 
    ? "desktop" 
    : isOpen 
      ? "mobileOpen" 
      : "mobileClosed";

  return (
    <>
      {/* Sidebar */}
      <motion.div
        initial={false}
        animate={currentVariant}
        variants={sidebarVariants}
        transition={{ duration: 0.3, ease: "easeInOut" }}
        className={`fixed top-0 left-0 z-30 h-screen overflow-hidden border-r border-gray-100 bg-white md:sticky ${
          isDesktop || isOpen ? "flex" : "hidden"
        }`}
      >
        <div className="flex h-full w-64 flex-shrink-0 flex-col overflow-hidden p-5">
          <div className="mb-6 flex items-center justify-between">
            <button
              onClick={toggle}
              className="cursor-pointer rounded-full p-2 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 md:hidden"
              aria-label="Close sidebar"
            >
              <X size={20} />
            </button>
          </div>

          <div className="flex-grow overflow-y-auto">{children}</div>
        </div>
      </motion.div>

      {/* Menu Toggle Button - Only show on mobile */}
      <button
        onClick={toggle}
        className={`fixed top-4 left-4 z-40 cursor-pointer rounded-md p-2 transition-all duration-300 md:hidden ${
          isOpen
            ? "pointer-events-none opacity-0"
            : "border border-gray-200 bg-white opacity-100 shadow-sm hover:bg-gray-50"
        }`}
        aria-label="Toggle navigation"
      >
        <PanelLeftClose size={20} />
      </button>

      {/* Overlay Background - Only show on mobile */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-20 bg-black/60 backdrop-blur-sm md:hidden"
            onClick={toggle}
            aria-hidden="true"
          />
        )}
      </AnimatePresence>
    </>
  );
};

export default Sidebar;
