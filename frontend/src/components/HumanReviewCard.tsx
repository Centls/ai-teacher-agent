import React, { useState } from "react";
import { Check, X, RefreshCw, Globe, XCircle, ChevronDown, ChevronRight, BookOpen } from "lucide-react";

interface HumanReviewCardProps {
  args: {
    question?: string;
    retrieved_docs?: string;
    source_type?: string;
    source_label?: string;
    message?: string;
  };
  id: string;
  onApprove: (id: string) => void;
  onDeny: (id: string, action?: "retry" | "web_search" | "cancel") => void;
}

/**
 * 人工审批卡片组件
 * 显示检索结果预览，让用户决定是否基于这些内容生成回答
 */
export const HumanReviewCard: React.FC<HumanReviewCardProps> = ({
  args,
  id,
  onApprove,
  onDeny,
}) => {
  const [showDenyOptions, setShowDenyOptions] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  const { source_label, retrieved_docs, message } = args;

  // 来源类型图标
  const getSourceIcon = () => {
    const sourceType = args.source_type || "unknown";
    switch (sourceType) {
      case "knowledge_base":
        return <BookOpen className="h-5 w-5 text-blue-600" />;
      case "web_search":
        return <Globe className="h-5 w-5 text-green-600" />;
      case "hybrid":
        return <div className="flex gap-1"><BookOpen className="h-4 w-4 text-blue-600" /><Globe className="h-4 w-4 text-green-600" /></div>;
      default:
        return <BookOpen className="h-5 w-5 text-gray-600" />;
    }
  };

  const handleDenyClick = () => {
    console.log("[HumanReviewCard] handleDenyClick called, setting showDenyOptions to true");
    setShowDenyOptions(true);
  };

  // 调试: 组件挂载/状态变化
  console.log("[HumanReviewCard] Render - showDenyOptions:", showDenyOptions, "id:", id);

  const handleDenyOption = (action: "retry" | "web_search" | "cancel") => {
    onDeny(id, action);
    setShowDenyOptions(false);
  };

  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50/50 p-4">
      {/* 标题区域 */}
      <div className="flex items-center gap-2 mb-3">
        {getSourceIcon()}
        <span className="font-medium text-gray-800">{source_label || "数据来源"}</span>
      </div>

      {/* 提示信息 */}
      <p className="text-sm text-gray-600 mb-3">
        {message || "请审核检索到的内容是否相关，确认后将基于这些内容生成回答。"}
      </p>

      {/* 检索结果预览 */}
      {retrieved_docs && (
        <div className="mb-4">
          <button
            className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-800 mb-2"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {isExpanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
            查看检索内容
          </button>
          {isExpanded && (
            <div className="rounded bg-white border border-gray-200 p-3 max-h-60 overflow-y-auto text-sm text-gray-700 whitespace-pre-wrap">
              {retrieved_docs}
            </div>
          )}
        </div>
      )}

      {/* 操作按钮 */}
      {!showDenyOptions ? (
        <div className="flex justify-end gap-2">
          <button
            onClick={handleDenyClick}
            className="flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-4 py-2 text-sm font-medium text-red-700 transition-colors hover:bg-red-50"
          >
            <X className="h-4 w-4" />
            拒绝
          </button>
          <button
            onClick={() => onApprove(id)}
            className="flex items-center gap-1.5 rounded-lg border border-green-200 bg-green-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-green-700"
          >
            <Check className="h-4 w-4" />
            确认生成
          </button>
        </div>
      ) : (
        /* 拒绝后的选项 */
        <div className="space-y-2">
          <p className="text-sm text-gray-600 mb-2">请选择后续操作：</p>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => handleDenyOption("retry")}
              className="flex items-center gap-1.5 rounded-lg border border-blue-200 bg-white px-3 py-2 text-sm font-medium text-blue-700 transition-colors hover:bg-blue-50"
            >
              <RefreshCw className="h-4 w-4" />
              重新检索
            </button>
            <button
              onClick={() => handleDenyOption("web_search")}
              className="flex items-center gap-1.5 rounded-lg border border-green-200 bg-white px-3 py-2 text-sm font-medium text-green-700 transition-colors hover:bg-green-50"
            >
              <Globe className="h-4 w-4" />
              Web 搜索
            </button>
            <button
              onClick={() => handleDenyOption("cancel")}
              className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
            >
              <XCircle className="h-4 w-4" />
              取消
            </button>
          </div>
          <button
            onClick={() => setShowDenyOptions(false)}
            className="text-sm text-gray-500 hover:text-gray-700 mt-1"
          >
            ← 返回
          </button>
        </div>
      )}
    </div>
  );
};