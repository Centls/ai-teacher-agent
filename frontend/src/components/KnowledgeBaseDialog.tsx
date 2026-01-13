import React, { useEffect, useState, useRef } from "react";
import { X, Upload, Trash2, FileText, Loader2, Database, Tag, Pencil, Check, XCircle } from "lucide-react";
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
}

interface KnowledgeBaseDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

export const KnowledgeBaseDialog = ({ isOpen, onClose }: KnowledgeBaseDialogProps) => {
  const [docs, setDocs] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedType, setSelectedType] = useState<KnowledgeType>("product_raw");
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [editingDocId, setEditingDocId] = useState<string | null>(null);
  const [editingType, setEditingType] = useState<KnowledgeType>("product_raw");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch documents when dialog opens
  useEffect(() => {
    if (isOpen) {
      fetchDocuments();
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

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setIsUploading(true);
    try {
      const file = files[0];
      const formData = new FormData();
      formData.append("file", file);
      formData.append("knowledge_type", selectedType);

      const response = await fetch("/api/agent/knowledge", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Upload failed");
      }

      // Refresh list and reset form
      await fetchDocuments();
      setShowUploadForm(false);
      alert("文件上传成功！");
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
    if (!confirm(`Are you sure you want to delete "${filename}"?`)) return;

    try {
      const response = await fetch(`/api/agent/knowledge/${id}`, {
        method: "DELETE",
      });

      if (!response.ok) {
        throw new Error("Delete failed");
      }

      // Refresh list
      await fetchDocuments();
    } catch (error) {
      console.error("Delete error:", error);
      alert("Failed to delete file.");
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

      // Refresh list and exit edit mode
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
    return new Date(isoString).toLocaleString();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="w-full max-w-5xl rounded-lg bg-white shadow-xl dark:bg-gray-900 flex flex-col max-h-[80vh]">
        {/* Header */}
        <div className="flex items-center justify-between border-b px-6 py-4 dark:border-gray-800">
          <div className="flex items-center gap-2">
            <Database className="h-5 w-5 text-blue-600" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Knowledge Base Management
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
          <div className="mb-6 flex items-center justify-between">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              管理用于 RAG 检索的永久知识库文档。
            </p>
            <Button
              onClick={() => setShowUploadForm(!showUploadForm)}
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
              <div className="flex items-center gap-4">
                <div className="flex-1">
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
                <div className="flex items-end gap-2">
                  <input
                    ref={fileInputRef}
                    type="file"
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

          {isLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
            </div>
          ) : docs.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed py-12 text-center">
              <div className="rounded-full bg-gray-100 p-3 dark:bg-gray-800">
                <FileText className="h-6 w-6 text-gray-400" />
              </div>
              <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">
                No documents found
              </h3>
              <p className="mt-1 text-sm text-gray-500">
                Upload documents to get started.
              </p>
            </div>
          ) : (
            <div className="overflow-hidden rounded-lg border dark:border-gray-800">
              <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-800">
                <thead className="bg-gray-50 dark:bg-gray-800/50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      文件名
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      类型
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      大小
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                      上传时间
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                      操作
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white dark:divide-gray-800 dark:bg-gray-900">
                  {docs.map((doc) => (
                    <tr key={doc.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                      <td className="whitespace-nowrap px-6 py-4">
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-gray-400" />
                          <span className="text-sm font-medium text-gray-900 dark:text-white">
                            {doc.filename}
                          </span>
                        </div>
                      </td>
                      <td className="whitespace-nowrap px-6 py-4">
                        {editingDocId === doc.id ? (
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
                              onClick={() => handleUpdateType(doc.id)}
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
                        ) : (
                          <span
                            className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-1 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 cursor-pointer hover:bg-blue-200 dark:hover:bg-blue-900/50"
                            onClick={() => handleStartEdit(doc)}
                            title="点击修改类型"
                          >
                            <Tag className="h-3 w-3" />
                            {doc.knowledge_type ? KNOWLEDGE_TYPES[doc.knowledge_type] : "未分类"}
                            <Pencil className="h-3 w-3 ml-1 opacity-50" />
                          </span>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                        {formatSize(doc.file_size)}
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                        {formatDate(doc.upload_time)}
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 text-right text-sm font-medium">
                        <button
                          onClick={() => handleDelete(doc.id, doc.filename)}
                          className="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        
        {/* Footer */}
        <div className="border-t bg-gray-50 px-6 py-4 dark:bg-gray-800/50 dark:border-gray-800 flex justify-end">
           <Button variant="outline" onClick={onClose}>关闭</Button>
        </div>
      </div>
    </div>
  );
};
