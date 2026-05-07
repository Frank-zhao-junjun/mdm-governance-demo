import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Save, Send, ArrowLeft, AlertTriangle, CheckCircle, Upload, FileText } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { api, upload as uploadApi } from '@/lib/api';
import type { Classification, AttributeTemplate, ValidationResult, DedupResult, Application, ApplicationAttachment } from '@/types/api';

const NewApplication: React.FC = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [majorClasses, setMajorClasses] = useState<Classification[]>([]);
  const [middleClasses, setMiddleClasses] = useState<Classification[]>([]);
  const [minorClasses, setMinorClasses] = useState<Classification[]>([]);
  const [templates, setTemplates] = useState<AttributeTemplate[]>([]);
  const [selectedMajor, setSelectedMajor] = useState('');
  const [selectedMiddle, setSelectedMiddle] = useState('');
  const [selectedMinor, setSelectedMinor] = useState('');
  const selectedClass = selectedMinor || selectedMiddle || selectedMajor;
  const [formData, setFormData] = useState({
    material_name: '',
    material_desc: '',
    classification_id: '',
    material_type: 'raw' as string,
    attribute_values: {} as Record<string, unknown>,
  });
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [dedupResult, setDedupResult] = useState<DedupResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [appId, setAppId] = useState('');
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [attachments, setAttachments] = useState<ApplicationAttachment[]>([]);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    api<Classification[]>('/api/classifications/?level=1')
      .then((data) => setMajorClasses(data || []));
  }, []);

  useEffect(() => {
    setSelectedMiddle('');
    setSelectedMinor('');
    setMiddleClasses([]);
    setMinorClasses([]);
    if (selectedMajor) {
      api<Classification[]>(`/api/classifications/?level=2&parent_id=${selectedMajor}`)
        .then((data) => setMiddleClasses(data || []));
    }
  }, [selectedMajor]);

  useEffect(() => {
    setSelectedMinor('');
    setMinorClasses([]);
    if (selectedMiddle) {
      api<Classification[]>(`/api/classifications/?level=3&parent_id=${selectedMiddle}`)
        .then((data) => setMinorClasses(data || []));
    }
  }, [selectedMiddle]);

  useEffect(() => {
    if (selectedClass) {
      api<AttributeTemplate[]>(`/api/classifications/${selectedClass}/templates`)
        .then((data) => setTemplates(data || []));
    } else {
      setTemplates([]);
    }
  }, [selectedClass]);

  const uploadFiles = async (targetAppId: string, files: File[]) => {
    if (files.length === 0) return [];
    setUploading(true);
    try {
      const uploaded: ApplicationAttachment[] = [];
      for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);
        uploaded.push(await uploadApi<ApplicationAttachment>(`/api/applications/${targetAppId}/attachments`, formData));
      }
      setAttachments((prev) => [...prev, ...uploaded]);
      setPendingFiles([]);
      toast.success(`已上传 ${uploaded.length} 个附件`);
      return uploaded;
    } finally {
      setUploading(false);
    }
  };

  const handleSaveDraft = async () => {
    if (!selectedClass) {
      toast.error('请选择物料分类');
      return;
    }
    setLoading(true);
    try {
      const payload = { ...formData, classification_id: selectedClass };
      const data = await api<Application>('/api/applications/', { method: 'POST', body: payload });
      setAppId(data.id);
      setAttachments(data.attachments || []);
      await uploadFiles(data.id, pendingFiles);
      toast.success('草稿已保存');
    } catch {
      // Error handled by api client
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!appId) {
      toast.error('请先保存草稿');
      return;
    }
    setLoading(true);
    try {
      const data = await api<{ success: boolean; material_code: string; validation: ValidationResult; duplicate_check: DedupResult }>(
        `/api/applications/${appId}/submit`,
        { method: 'POST' }
      );
      setValidationResult(data.validation);
      setDedupResult(data.duplicate_check);
      if (data.success) {
        toast.success(`提交成功！物料编码: ${data.material_code}`);
        navigate(`/applications/${appId}`);
      }
    } catch {
      // Error handled by api client
    } finally {
      setLoading(false);
    }
  };

  const updateField = (field: string, value: unknown) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const updateAttr = (field: string, value: unknown) => {
    setFormData((prev) => ({ ...prev, attribute_values: { ...prev.attribute_values, [field]: value } }));
  };

  const handleFilesSelected = async (files: FileList | null) => {
    const selectedFiles = Array.from(files || []);
    if (selectedFiles.length === 0) return;
    if (appId) {
      try {
        await uploadFiles(appId, selectedFiles);
      } catch {
        toast.error('附件上传失败');
      }
    } else {
      setPendingFiles((prev) => [...prev, ...selectedFiles]);
      toast.info('附件将在保存草稿后上传');
    }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center gap-4">
        <Button variant="ghost" onClick={() => navigate('/applications')}><ArrowLeft className="w-4 h-4 mr-2" />返回</Button>
        <h2 className="text-xl font-semibold">新增物料申请</h2>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">基本信息</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>物料名称 <span className="text-red-500">*</span></Label>
              <Input placeholder="例如：乙醇 95% 工业级" value={formData.material_name} onChange={(e) => updateField('material_name', e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>物料类型 <span className="text-red-500">*</span></Label>
              <Select value={formData.material_type} onValueChange={(v) => updateField('material_type', v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="raw">原材料</SelectItem>
                  <SelectItem value="semi">半成品</SelectItem>
                  <SelectItem value="finished">成品</SelectItem>
                  <SelectItem value="auxiliary">辅助材料</SelectItem>
                  <SelectItem value="spare">备品备件</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label>大类 <span className="text-red-500">*</span></Label>
              <Select value={selectedMajor} onValueChange={setSelectedMajor}>
                <SelectTrigger><SelectValue placeholder="选择大类" /></SelectTrigger>
                <SelectContent>
                  {majorClasses.map((c) => (
                    <SelectItem key={c.id} value={c.id}>{c.name} ({c.code})</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>中类</Label>
              <Select value={selectedMiddle} onValueChange={setSelectedMiddle} disabled={!selectedMajor || middleClasses.length === 0}>
                <SelectTrigger><SelectValue placeholder="选择中类" /></SelectTrigger>
                <SelectContent>
                  {middleClasses.map((c) => (
                    <SelectItem key={c.id} value={c.id}>{c.name} ({c.code})</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>小类</Label>
              <Select value={selectedMinor} onValueChange={setSelectedMinor} disabled={!selectedMiddle || minorClasses.length === 0}>
                <SelectTrigger><SelectValue placeholder="选择小类" /></SelectTrigger>
                <SelectContent>
                  {minorClasses.map((c) => (
                    <SelectItem key={c.id} value={c.id}>{c.name} ({c.code})</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-2">
            <Label>物料描述</Label>
            <Textarea placeholder="详细描述物料的用途、特性等" value={formData.material_desc} onChange={(e) => updateField('material_desc', e.target.value)} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">图纸与附件</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            <Input ref={fileInputRef} className="hidden" type="file" multiple onChange={(e) => handleFilesSelected(e.target.files)} />
            <Button type="button" variant="outline" disabled={uploading} onClick={() => fileInputRef.current?.click()}>
              <Upload className="w-4 h-4 mr-2" />{uploading ? '上传中...' : '选择附件'}
            </Button>
          </div>
          {(pendingFiles.length > 0 || attachments.length > 0) && (
            <div className="space-y-2">
              {pendingFiles.map((file, index) => (
                <div key={`${file.name}-${index}`} className="flex items-center gap-2 text-sm text-amber-700 bg-amber-50 rounded-lg px-3 py-2">
                  <FileText className="w-4 h-4" />
                  <span>{file.name}</span>
                  <span className="text-xs text-amber-600">待保存后上传</span>
                </div>
              ))}
              {attachments.map((file) => (
                <div key={file.id} className="flex items-center gap-2 text-sm text-gray-700 bg-gray-50 rounded-lg px-3 py-2">
                  <FileText className="w-4 h-4" />
                  <span>{file.original_name}</span>
                  <span className="text-xs text-gray-500">{Math.ceil(file.size / 1024)} KB</span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {selectedClass && templates.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">分类属性</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            {templates.map((t) => (
              <div key={t.id} className="space-y-2">
                <Label>{t.field_label}{t.is_required && <span className="text-red-500 ml-1">*</span>}</Label>
                {t.field_type === 'select' ? (
                  <Select onValueChange={(v) => updateAttr(t.field_name, v)}>
                    <SelectTrigger><SelectValue placeholder={`选择${t.field_label}`} /></SelectTrigger>
                    <SelectContent>{(t.options || []).map((opt) => <SelectItem key={opt} value={opt}>{opt}</SelectItem>)}</SelectContent>
                  </Select>
                ) : t.field_type === 'number' ? (
                  <Input type="number" onChange={(e) => updateAttr(t.field_name, e.target.value)} />
                ) : t.field_type === 'date' ? (
                  <Input type="date" onChange={(e) => updateAttr(t.field_name, e.target.value)} />
                ) : t.field_type === 'boolean' ? (
                  <Select onValueChange={(v) => updateAttr(t.field_name, v === 'true')}>
                    <SelectTrigger><SelectValue placeholder="选择" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="true">是</SelectItem>
                      <SelectItem value="false">否</SelectItem>
                    </SelectContent>
                  </Select>
                ) : (
                  <Input placeholder={t.description || ''} onChange={(e) => updateAttr(t.field_name, e.target.value)} />
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {validationResult && (
        <Card className={validationResult.passed ? 'border-green-200' : 'border-red-200'}>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              {validationResult.passed ? <CheckCircle className="w-5 h-5 text-green-500" /> : <AlertTriangle className="w-5 h-5 text-red-500" />}
              质量校验结果
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {validationResult.checks.map((check, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  {check.passed ? <CheckCircle className="w-4 h-4 text-green-500" /> : <AlertTriangle className="w-4 h-4 text-red-500" />}
                  <span>{check.message}</span>
                </div>
              ))}
            </div>
            {validationResult.errors.length > 0 && (
              <div className="mt-3 p-3 bg-red-50 rounded-lg">
                <p className="text-red-700 font-medium">错误:</p>
                {validationResult.errors.map((err, i) => <p key={i} className="text-red-600 text-sm">{err}</p>)}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {dedupResult && dedupResult.is_duplicate && (
        <Card className="border-yellow-200">
          <CardHeader><CardTitle className="text-base flex items-center gap-2"><AlertTriangle className="w-5 h-5 text-yellow-500" />重复预检警告</CardTitle></CardHeader>
          <CardContent>
            <p className="text-sm text-gray-600 mb-2">发现 {dedupResult.similar_materials?.length || 0} 个相似物料（置信度: {Math.round((dedupResult.confidence || 0) * 100)}%）</p>
            <div className="space-y-2">
              {(dedupResult.similar_materials || []).map((m, i) => (
                <div key={i} className="p-2 bg-yellow-50 rounded-lg text-sm">
                  <Badge variant="outline" className="mb-1">{m.material_code}</Badge>
                  <p>{m.material_name}</p>
                  <p className="text-gray-500">{m.reason}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="flex gap-4">
        <Button variant="outline" onClick={handleSaveDraft} disabled={loading || uploading}><Save className="w-4 h-4 mr-2" />保存草稿</Button>
        <Button className="bg-blue-600 hover:bg-blue-700" onClick={handleSubmit} disabled={loading || uploading}><Send className="w-4 h-4 mr-2" />{loading ? '处理中...' : '提交申请'}</Button>
      </div>
    </div>
  );
};

export default NewApplication;