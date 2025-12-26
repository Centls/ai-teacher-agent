import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Bot, Settings, Plus } from "lucide-react";

const teachers = [
  { id: "marketing", name: "Marketing Teacher", role: "Marketing Specialist" },
  { id: "support", name: "Support Teacher", role: "Customer Support" },
  { id: "researcher", name: "Researcher", role: "Deep Research" },
];

interface SidebarProps {
  selectedTeacher: string;
  onSelectTeacher: (id: string) => void;
  className?: string;
  onClose?: () => void;
}

export function Sidebar({ selectedTeacher, onSelectTeacher, className, onClose }: SidebarProps) {
  const handleSelect = (id: string) => {
    onSelectTeacher(id);
    if (onClose) onClose();
  };

  return (
    <div className={`w-64 border-r bg-slate-50/50 flex flex-col h-full ${className}`}>
      <div className="p-4 border-b">
        <h2 className="font-semibold text-lg flex items-center gap-2">
          <Bot className="w-5 h-5" />
          Nexus
        </h2>
      </div>
      
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-2">
          <h3 className="text-xs font-medium text-slate-500 mb-2 uppercase tracking-wider">Teachers</h3>
          {teachers.map((teacher) => (
            <Button
              key={teacher.id}
              variant={selectedTeacher === teacher.id ? "secondary" : "ghost"}
              className={`w-full justify-start gap-2 ${selectedTeacher === teacher.id ? "bg-slate-200" : ""}`}
              onClick={() => handleSelect(teacher.id)}
            >
              <div className={`w-2 h-2 rounded-full ${selectedTeacher === teacher.id ? "bg-blue-500" : "bg-slate-300"}`} />
              <div className="flex flex-col items-start text-left">
                <span className="text-sm font-medium">{teacher.name}</span>
                <span className="text-xs text-slate-500">{teacher.role}</span>
              </div>
            </Button>
          ))}
        </div>
      </ScrollArea>

      <div className="p-4 border-t space-y-2">
        <Button variant="outline" className="w-full justify-start gap-2">
          <Plus className="w-4 h-4" />
          New Session
        </Button>
        <Button variant="ghost" className="w-full justify-start gap-2">
          <Settings className="w-4 h-4" />
          Settings
        </Button>
      </div>
    </div>
  );
}
