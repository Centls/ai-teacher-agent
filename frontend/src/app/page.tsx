'use client';

import { useState } from "react";
import { ChatInterface } from "@/components/chat-interface";
import { Sidebar } from "@/components/sidebar";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Menu } from "lucide-react";

export default function Home() {
  const [selectedTeacher, setSelectedTeacher] = useState("marketing");
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  return (
    <main className="flex min-h-screen bg-slate-50">
      {/* Desktop Sidebar */}
      <div className="hidden md:block h-screen sticky top-0">
        <Sidebar selectedTeacher={selectedTeacher} onSelectTeacher={setSelectedTeacher} />
      </div>

      <div className="flex-1 flex flex-col h-screen">
        {/* Mobile Header */}
        <div className="md:hidden p-4 border-b bg-white flex items-center justify-between sticky top-0 z-10">
          <h1 className="font-semibold text-lg">Nexus</h1>
          <Sheet open={isMobileOpen} onOpenChange={setIsMobileOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon">
                <Menu className="w-6 h-6" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="p-0 w-72">
              <Sidebar 
                selectedTeacher={selectedTeacher} 
                onSelectTeacher={setSelectedTeacher} 
                className="w-full border-none"
                onClose={() => setIsMobileOpen(false)}
              />
            </SheetContent>
          </Sheet>
        </div>

        {/* Main Content */}
        <div className="flex-1 overflow-hidden">
          <ChatInterface selectedTeacher={selectedTeacher} />
        </div>
      </div>
    </main>
  );
}
