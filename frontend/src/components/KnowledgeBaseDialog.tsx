import React, { useEffect, useState, useRef, useMemo } from "react";
import { X, Upload, Trash2, FileText, Loader2, Database, Tag, Pencil, Check, XCircle, Folder, ChevronRight, Plus, Home } from "lucide-react";
import { Button } from "./ui/button";

// 知识类型定义 (与后端 server.py 保持一致)
const KNOWLEDGE_TYPES = {
  product_raw: "产品原始资料",
  sales_raw: "销售经验/话术",
  material: "文案/素材",
  conclusion: "结论型知识",
} as const;

type KnowledgeType = keyof typeof KNOWLEDGE_TYPES;

interface Document {
  id: string;
  filename: string;
  upload_time: string;
  file_size: number;
  status: string;
  knowledge_type?: KnowledgeType;
  folder?: string;
}

interface KnowledgeBaseDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

// 列表项类型：文件夹或文件
interface ListItem {
  type: "folder" | "file";
  name: string;
  path: string;
  // 文件专属字段
  doc?: Document;
}

// 获取当前路径下的直接子文件夹
function getDirectSubFolders(allFolders: string[], currentPath: string): string[] {
  const subFolders = new Set<string>();
  const prefix = currentPath ? currentPath + "/" : "";

  for (const folder of allFolders) {
    if (currentPath === "") {
      // 根目录：获取顶层文件夹
      const firstPart = folder.split("/")[0];
      if (firstPart) {
        subFolders.add(firstPart);
      }
    } else if (folder.startsWith(prefix)) {
      // 子目录：获取下一层文件夹
      const remaining = folder.slice(prefix.length);
      const nextPart = remaining.split("/")[0];
      if (nextPart && folder !== currentPath) {
        subFolders.add(nextPart);
      }
    }
  }

  return Array.from(subFolders).sort();
}

export const KnowledgeBaseDialog = ({ isOpen, onClose }: KnowledgeBaseDialogProps) => {
  const [docs, setDocs] = useState<Document[]>([]);
  const [folders, setFolders] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedType, setSelectedType] = useState<KnowledgeType>("product_raw");
  const [selectedFolder, setSelectedFolder] = useState<string>("");
  const [newFolderName, setNewFolderName] = useState<string>("");
  const [showNewFolderInput, setShowNewFolderInput] = useState(false);
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [editingDocId, setEditingDocId] = useState<string | null>(null);
  const [editingType, setEditingType] = useState<KnowledgeType>("product_raw");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isBatchProcessing, setIsBatchProcessing] = useState(false);
  const [currentPath, setCurrentPath] = useState<string>(""); // 当前浏览路径，"" 表示根目录
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch documents and folders when dialog opens
  useEffect(() => {
    if (isOpen) {
      fetchDocuments();
      fetchFolders();
      setSelectedIds(new Set());
      setCurrentPath("");
    }
  }, [isOpen]);

  const fetchDocuments = async () => {
    setIsLoading(true);
    try {
      const res = await fetch("/api/agent/knowledge/list");
      if (res.ok) {
        const data = await res.json();
        setDocs(data);
      }
    } catch (error) {
      console.error("Failed to fetch documents:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchFolders = async () => {
    try {
      const res = await fetch("/api/agent/knowledge/folders");
      if (res.ok) {
        const data = await res.json();
        setFolders(data);
      }
    } catch (error) {
      console.error("Failed to fetch folders:", error);
    }
  };

  // 计算当前路径下的列表项（文件夹 + 文件混排，文件夹在前）
  const currentItems = useMemo<ListItem[]>(() => {
    // 1. 获取当前路径下的直接子文件夹
    const subFolderNames = getDirectSubFolders(folders, currentPath);
    const folderItems: ListItem[] = subFolderNames.map((name) => ({
      type: "folder",
      name,
      path: currentPath ? `${currentPath}/${name}` : name,
    }));

    // 2. 获取当前路径下的文件（folder 完全匹配当前路径）
    const filesInPath = docs.filter((d) => {
      const docFolder = d.folder || "";
      return docFolder === currentPath;
    });
    const fileItems: ListItem[] = filesInPath.map((doc) => ({
      type: "file",
      name: doc.filename,
      path: currentPath,
      doc,
    }));

    // 3. 合并：文件夹在前，文件在后
    return [...folderItems, ...fileItems];
  }, [folders, docs, currentPath]);

  // 面包屑导航数据
  const breadcrumbs = useMemo(() => {
    if (!currentPath) return [];
    return currentPath.split("/");
  }, [currentPath]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setIsUploading(true);
    try {
      const formData = new FormData();
      Array.from(files).forEach((file) => {
        formData.append("files", file);
      });
      formData.append("knowledge_type", selectedType);

      // 使用当前路径或新建文件夹
      const folderToUse = showNewFolderInput && newFolderName.trim()
        ? (selectedFolder ? `${selectedFolder}/${newFolderName.trim()}` : newFolderName.trim())
        : selectedFolder;
      if (folderToUse) {
        formData.append("folder", folderToUse);
      }

      const response = await fetch("/api/agent/upload/knowledge", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Upload failed");
      }

      const result = await response.json();
      console.log("Upload result:", result);

      await fetchDocuments();
      await fetchFolders();
      setShowUploadForm(false);
      setShowNewFolderInput(false);
      setNewFolderName("");
      alert(`成功上传 ${result.results?.length || 0} 个文件！`);
    } catch (error) {
      console.error("Upload error:", error);
      alert("文件上传失败。");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleDelete = async (id: string, filename: string) => {
    if (!confirm(`确定要删除 "${filename}" 吗？`)) return;

    try {
      const response = await fetch(`/api/agent/knowledge/${id}`, {
        method: "DELETE",
      });

      if (!response.ok) {
        throw new Error("Delete failed");
      }

      await fetchDocuments();
      if (selectedIds.has(id)) {
        const newSelected = new Set(selectedIds);
        newSelected.delete(id);
        setSelectedIds(newSelected);
      }
    } catch (error) {
      console.error("Delete error:", error);
      alert("删除文件失败。");
    }
  };

  // 删除文件夹及其所有文件
  const handleDeleteFolder = async (folderPath: string) => {
    // 计算该文件夹下的文件数量
    const filesInFolder = docs.filter((d) => {
      const docFolder = d.folder || "";
      return docFolder === folderPath || docFolder.startsWith(folderPath + "/");
    });

    if (!confirm(`确定要删除文件夹 "${folderPath}" 及其 ${filesInFolder.length} 个文件吗？\n\n此操作不可撤销！`)) {
      return;
    }

    try {
      const response = await fetch(`/api/agent/knowledge/folders/${encodeURIComponent(folderPath)}`, {
        method: "DELETE",
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || "删除文件夹失败");
      }

      const result = await response.json();
      alert(result.message || `已删除文件夹 "${folderPath}"`);

      await fetchDocuments();
      await fetchFolders();
    } catch (error: any) {
      console.error("Delete folder error:", error);
      alert(error.message || "删除文件夹失败");
    }
  };

  const handleBatchDelete = async () => {
    if (selectedIds.size === 0) return;
    if (!confirm(`确定要删除选中的 ${selectedIds.size} 个文件吗？`)) return;

    setIsBatchProcessing(true);
    try {
      const response = await fetch("/api/agent/knowledge/batch/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: Array.from(selectedIds) }),
      });

      if (!response.ok) throw new Error("Batch delete failed");

      await fetchDocuments();
      await fetchFolders();
      setSelectedIds(new Set());
    } catch (error) {
      console.error("Batch delete error:", error);
      alert("批量删除失败");
    } finally {
      setIsBatchProcessing(false);
    }
  };

  const handleBatchUpdateType = async (newType: KnowledgeType) => {
    if (selectedIds.size === 0) return;

    setIsBatchProcessing(true);
    try {
      const response = await fetch("/api/agent/knowledge/batch/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ids: Array.from(selectedIds),
          knowledge_type: newType,
        }),
      });

      if (!response.ok) throw new Error("Batch update failed");

      await fetchDocuments();
      setSelectedIds(new Set());
    } catch (error) {
      console.error("Batch update error:", error);
      alert("批量修改失败");
    } finally {
      setIsBatchProcessing(false);
    }
  };

  const toggleSelect = (id: string) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
  };

  // 只选择当前目录下的文件
  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      const fileIds = currentItems
        .filter((item) => item.type === "file" && item.doc)
        .map((item) => item.doc!.id);
      setSelectedIds(new Set(fileIds));
    } else {
      setSelectedIds(new Set());
    }
  };

  const handleStartEdit = (doc: Document) => {
    setEditingDocId(doc.id);
    setEditingType(doc.knowledge_type || "product_raw");
  };

  const handleCancelEdit = () => {
    setEditingDocId(null);
  };

  const handleUpdateType = async (id: string) => {
    try {
      const response = await fetch(`/api/agent/knowledge/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ knowledge_type: editingType }),
      });

      if (!response.ok) {
        throw new Error("Update failed");
      }

      await fetchDocuments();
      setEditingDocId(null);
    } catch (error) {
      console.error("Update error:", error);
      alert("修改类型失败");
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  const formatDate = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleDateString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // 进入文件夹
  const navigateToFolder = (folderPath: string) => {
    setCurrentPath(folderPath);
    setSelectedIds(new Set()); // 切换目录时清空选择
  };

  // 返回上级目录
  const navigateUp = () => {
    if (!currentPath) return;
    const parts = currentPath.split("/");
    parts.pop();
    setCurrentPath(parts.join("/"));
    setSelectedIds(new Set());
  };

  // 导航到面包屑指定层级
  const navigateToBreadcrumb = (index: number) => {
    if (index < 0) {
      setCurrentPath("");
    } else {
      const parts = currentPath.split("/");
      setCurrentPath(parts.slice(0, index + 1).join("/"));
    }
    setSelectedIds(new Set());
  };

  // 当前目录下的文件数量（用于全选）
  const filesInCurrentDir = currentItems.filter((item) => item.type === "file").length;

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="w-full max-w-5xl rounded-lg bg-white shadow-xl dark:bg-gray-900 flex flex-col max-h-[80vh]">
        {/* Header */}
        <div className="flex items-center justify-between border-b px-6 py-4 dark:border-gray-800">
          <div className="flex items-center gap-2">
            <Database className="h-5 w-5 text-blue-600" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              知识库管理
            </h2>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-1 hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            <X className="h-5 w-5 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          <div className="mb-4 flex items-center justify-between">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              管理用于 RAG 检索的永久知识库文档。
            </p>
            <Button
              onClick={() => {
                setShowUploadForm(!showUploadForm);
                // 上传时默认使用当前路径
                setSelectedFolder(currentPath);
              }}
              disabled={isUploading}
              className="gap-2"
            >
              <Upload className="h-4 w-4" />
              上传文档
            </Button>
          </div>

          {/* Upload Form */}
          {showUploadForm && (
            <div className="mb-6 rounded-lg border bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800/50">
              <div className="flex flex-wrap items-end gap-4">
                {/* 知识类型选择 */}
                <div className="flex-1 min-w-[150px]">
                  <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                    知识类型
                  </label>
                  <select
                    value={selectedType}
                    onChange={(e) => setSelectedType(e.target.value as KnowledgeType)}
                    className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                  >
                    {Object.entries(KNOWLEDGE_TYPES).map(([key, label]) => (
                      <option key={key} value={key}>
                        {label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* 文件夹选择 */}
                <div className="flex-1 min-w-[200px]">
                  <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                    存放文件夹
                  </label>
                  <div className="flex items-center gap-2">
                    <select
                      value={selectedFolder}
                      onChange={(e) => setSelectedFolder(e.target.value)}
                      className="flex-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                    >
                      <option value="">根目录</option>
                      {folders.map((folder) => (
                        <option key={folder} value={folder}>
                          📁 {folder}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => setShowNewFolderInput(!showNewFolderInput)}
                      className="p-2 rounded-md border border-gray-300 hover:bg-gray-100 dark:border-gray-600 dark:hover:bg-gray-700"
                      title="新建文件夹"
                    >
                      <Plus className="h-4 w-4" />
                    </button>
                  </div>
                </div>

                {/* 新建文件夹输入 */}
                {showNewFolderInput && (
                  <div className="flex-1 min-w-[150px]">
                    <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                      新文件夹名称
                    </label>
                    <input
                      type="text"
                      value={newFolderName}
                      onChange={(e) => setNewFolderName(e.target.value)}
                      placeholder="输入文件夹名称"
                      className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                    />
                  </div>
                )}

                {/* 操作按钮 */}
                <div className="flex items-end gap-2">
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.html,.htm,.md,.markdown,.txt,.csv,.jpg,.jpeg,.png,.bmp,.gif,.tiff,.tif,.mp3,.wav,.m4a,.flac,.ogg"
                    onChange={handleFileUpload}
                    className="hidden"
                  />
                  <Button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isUploading}
                    className="gap-2"
                  >
                    {isUploading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Upload className="h-4 w-4" />
                    )}
                    选择文件
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => setShowUploadForm(false)}
                  >
                    取消
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Batch Actions Toolbar */}
          {selectedIds.size > 0 && (
            <div className="mb-4 flex items-center justify-between rounded-lg border border-blue-200 bg-blue-50 p-3 dark:border-blue-900 dark:bg-blue-900/20">
              <div className="flex items-center gap-2">
                <Check className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                <span className="text-sm font-medium text-blue-900 dark:text-blue-100">
                  已选择 {selectedIds.size} 项
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-2 border-r border-blue-200 pr-2 dark:border-blue-800">
                  <span className="text-xs text-blue-700 dark:text-blue-300">批量修改类型:</span>
                  <select
                    onChange={(e) => handleBatchUpdateType(e.target.value as KnowledgeType)}
                    className="rounded border border-blue-300 bg-white px-2 py-1 text-xs dark:border-blue-700 dark:bg-gray-800"
                    defaultValue=""
                  >
                    <option value="" disabled>选择类型...</option>
                    {Object.entries(KNOWLEDGE_TYPES).map(([key, label]) => (
                      <option key={key} value={key}>{label}</option>
                    ))}
                  </select>
                </div>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={handleBatchDelete}
                  disabled={isBatchProcessing}
                  className="h-8 gap-1"
                >
                  {isBatchProcessing ? <Loader2 className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
                  批量删除
                </Button>
              </div>
            </div>
          )}

          {/* 面包屑导航 */}
          <div className="mb-4 flex items-center gap-1 text-sm">
            <button
              onClick={() => navigateToBreadcrumb(-1)}
              className={`flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 ${
                currentPath === "" ? "text-blue-600 font-medium" : "text-gray-600 dark:text-gray-400"
              }`}
            >
              <Home className="h-4 w-4" />
              根目录
            </button>
            {breadcrumbs.map((crumb, index) => (
              <React.Fragment key={index}>
                <ChevronRight className="h-4 w-4 text-gray-400" />
                <button
                  onClick={() => navigateToBreadcrumb(index)}
                  className={`px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 ${
                    index === breadcrumbs.length - 1
                      ? "text-blue-600 font-medium"
                      : "text-gray-600 dark:text-gray-400"
                  }`}
                >
                  {crumb}
                </button>
              </React.Fragment>
            ))}
          </div>

          {isLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
            </div>
          ) : currentItems.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed py-12 text-center">
              <div className="rounded-full bg-gray-100 p-3 dark:bg-gray-800">
                <FileText className="h-6 w-6 text-gray-400" />
              </div>
              <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">
                {currentPath ? "此文件夹为空" : "知识库为空"}
              </h3>
              <p className="mt-1 text-sm text-gray-500">
                {currentPath ? "可以上传文档到此文件夹。" : "上传文档以开始使用。"}
              </p>
            </div>
          ) : (
            <div className="overflow-hidden rounded-lg border dark:border-gray-800">
              <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-800">
                <thead className="bg-gray-50 dark:bg-gray-800/50">
                  <tr>
                    <th className="px-4 py-3 text-left w-10">
                      <input
                        type="checkbox"
                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        checked={filesInCurrentDir > 0 && selectedIds.size === filesInCurrentDir}
                        onChange={(e) => handleSelectAll(e.target.checked)}
                        disabled={filesInCurrentDir === 0}
                      />
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      名称
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      类型
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      大小
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      时间
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                      操作
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white dark:divide-gray-800 dark:bg-gray-900">
                  {currentItems.map((item, index) => (
                    <tr
                      key={item.type === "folder" ? `folder-${item.path}` : `file-${item.doc?.id}`}
                      className={`hover:bg-gray-50 dark:hover:bg-gray-800/50 ${
                        item.type === "file" && item.doc && selectedIds.has(item.doc.id)
                          ? "bg-blue-50 dark:bg-blue-900/10"
                          : ""
                      } ${item.type === "folder" ? "cursor-pointer" : ""}`}
                      onClick={item.type === "folder" ? () => navigateToFolder(item.path) : undefined}
                    >
                      <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                        {item.type === "file" && item.doc ? (
                          <input
                            type="checkbox"
                            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                            checked={selectedIds.has(item.doc.id)}
                            onChange={() => toggleSelect(item.doc!.id)}
                          />
                        ) : (
                          <span className="text-gray-300">—</span>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3">
                        <div className="flex items-center gap-2">
                          {item.type === "folder" ? (
                            <Folder className="h-5 w-5 text-yellow-500" />
                          ) : (
                            <FileText className="h-4 w-4 text-gray-400" />
                          )}
                          <span className={`text-sm font-medium ${
                            item.type === "folder"
                              ? "text-gray-900 dark:text-white"
                              : "text-gray-700 dark:text-gray-300"
                          }`}>
                            {item.name}
                          </span>
                        </div>
                      </td>
                      <td className="whitespace-nowrap px-4 py-3" onClick={(e) => e.stopPropagation()}>
                        {item.type === "folder" ? (
                          <span className="text-xs text-gray-400">文件夹</span>
                        ) : item.doc && editingDocId === item.doc.id ? (
                          <div className="flex items-center gap-2">
                            <select
                              value={editingType}
                              onChange={(e) => setEditingType(e.target.value as KnowledgeType)}
                              className="rounded-md border border-gray-300 bg-white px-2 py-1 text-xs dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                            >
                              {Object.entries(KNOWLEDGE_TYPES).map(([key, label]) => (
                                <option key={key} value={key}>
                                  {label}
                                </option>
                              ))}
                            </select>
                            <button
                              onClick={() => handleUpdateType(item.doc!.id)}
                              className="text-green-600 hover:text-green-800 dark:text-green-400"
                              title="确认"
                            >
                              <Check className="h-4 w-4" />
                            </button>
                            <button
                              onClick={handleCancelEdit}
                              className="text-gray-500 hover:text-gray-700 dark:text-gray-400"
                              title="取消"
                            >
                              <XCircle className="h-4 w-4" />
                            </button>
                          </div>
                        ) : item.doc ? (
                          <span
                            className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-1 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 cursor-pointer hover:bg-blue-200 dark:hover:bg-blue-900/50"
                            onClick={() => handleStartEdit(item.doc!)}
                            title="点击修改类型"
                          >
                            <Tag className="h-3 w-3" />
                            {item.doc.knowledge_type ? KNOWLEDGE_TYPES[item.doc.knowledge_type] : "未分类"}
                            <Pencil className="h-3 w-3 ml-1 opacity-50" />
                          </span>
                        ) : null}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">
                        {item.type === "folder" ? (
                          <span className="text-gray-400">—</span>
                        ) : item.doc ? (
                          formatSize(item.doc.file_size)
                        ) : null}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">
                        {item.type === "folder" ? (
                          <span className="text-gray-400">—</span>
                        ) : item.doc ? (
                          formatDate(item.doc.upload_time)
                        ) : null}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-right text-sm font-medium" onClick={(e) => e.stopPropagation()}>
                        {item.type === "folder" ? (
                          <button
                            onClick={() => handleDeleteFolder(item.path)}
                            className="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300"
                            title="删除文件夹"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        ) : item.doc ? (
                          <button
                            onClick={() => handleDelete(item.doc!.id, item.doc!.filename)}
                            className="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300"
                            title="删除文件"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t bg-gray-50 px-6 py-4 dark:bg-gray-800/50 dark:border-gray-800 flex justify-between items-center">
          <div className="text-sm text-gray-500">
            共 {docs.length} 个文件，{folders.length} 个文件夹
          </div>
          <Button variant="outline" onClick={onClose}>关闭</Button>
        </div>
      </div>
    </div>
  );
};