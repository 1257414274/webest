<template>
  <div class="target-container">
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span>目标资产智能分类</span>
        </div>
      </template>
      
      <!-- 控制区 -->
      <div class="control-panel">
        <el-form :inline="true" :model="form" class="demo-form-inline">
          <el-form-item label="ICP备案主体">
            <el-input v-model="form.icp_keyword" placeholder="请输入ICP备案号或主体名称" clearable style="width: 250px" @keyup.enter="onSubmitPipeline" />
          </el-form-item>
          <el-form-item label="拉取数量">
            <el-input-number v-model="form.limit" :min="10" :max="10000" :step="100" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="onSubmitPipeline" :loading="isSubmitting" icon="Position">一键执行资产流水线</el-button>
            <el-button @click="fetchData" icon="Refresh">刷新结果</el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 搜索区 -->
      <div class="search-panel" style="margin-bottom: 20px;">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索 IP / 域名 / 公司"
          style="width: 300px"
          clearable
          @keyup.enter="fetchData"
        >
          <template #append>
            <el-button icon="Search" @click="fetchData" />
          </template>
        </el-input>
      </div>

      <!-- 数据展示区 -->
      <el-table :data="tableData" v-loading="loading" border style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="操作" width="200" fixed="left">
          <template #default="scope">
            <el-button
              type="primary"
              :disabled="scope.row.penetration_status === 'completed' || statusUpdatingSet.has(scope.row.id)"
              :loading="statusUpdatingSet.has(scope.row.id)"
              @click="onMarkPenetrated(scope.row)"
            >
              已渗透
            </el-button>
            <el-button link type="primary" @click="onCopyUrlAndAction(scope.row)">
              复制
            </el-button>
          </template>
        </el-table-column>
        <el-table-column prop="company" label="公司/主体" width="180" show-overflow-tooltip />
        <el-table-column prop="ip" label="IP地址" width="140" />
        <el-table-column prop="port" label="端口" width="80" />
        <el-table-column prop="domain" label="域名" width="180" show-overflow-tooltip />
        <el-table-column prop="url" label="URL" show-overflow-tooltip />
        <el-table-column prop="predicted_tactic" label="战术分类" width="150">
          <template #default="scope">
            <el-tag v-if="scope.row.predicted_tactic === 'admin_panels'" type="danger">管理后台</el-tag>
            <el-tag v-else-if="scope.row.predicted_tactic === 'high_risk_apps'" type="warning">高危应用</el-tag>
            <el-tag v-else-if="scope.row.predicted_tactic === 'high_risk_ports'" type="danger">高危端口</el-tag>
            <el-tag v-else-if="scope.row.predicted_tactic" type="info">{{ scope.row.predicted_tactic }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="confidence" label="置信度" width="100">
          <template #default="scope">
            <span v-if="scope.row.confidence">{{ (scope.row.confidence * 100).toFixed(1) }}%</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="deepseek_priority" label="优先级" width="130">
          <template #default="scope">
            <el-tag
              :type="normalizePriority(scope.row.deepseek_priority).type"
              :class="normalizePriority(scope.row.deepseek_priority).className"
              :style="normalizePriority(scope.row.deepseek_priority).style"
            >
              {{ normalizePriority(scope.row.deepseek_priority).text }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="deepseek_framework" label="框架/组件" width="160" show-overflow-tooltip>
          <template #default="scope">
            <span>{{ normalizeAction(scope.row.deepseek_framework) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="deepseek_reason" label="判断逻辑" min-width="260">
          <template #default="scope">
            <el-tooltip
              v-if="normalizeAction(scope.row.deepseek_reason).length > 60"
              :content="normalizeAction(scope.row.deepseek_reason)"
              placement="top-start"
            >
              <div class="action-text">{{ normalizeAction(scope.row.deepseek_reason) }}</div>
            </el-tooltip>
            <div v-else class="action-text">{{ normalizeAction(scope.row.deepseek_reason) }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="deepseek_action" label="最新建议操作" min-width="260">
          <template #default="scope">
            <el-tooltip
              v-if="normalizeAction(scope.row.deepseek_action).length > 60"
              :content="normalizeAction(scope.row.deepseek_action)"
              placement="top-start"
            >
              <div class="action-text">{{ normalizeAction(scope.row.deepseek_action) }}</div>
            </el-tooltip>
            <div v-else class="action-text">{{ normalizeAction(scope.row.deepseek_action) }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="penetration_status" label="状态" width="100">
          <template #default="scope">
            <span v-if="scope.row.penetration_status === 'completed'" class="status-done">已完成</span>
            <span v-else class="status-pending">未完成</span>
          </template>
        </el-table-column>
        <el-table-column prop="penetration_remark" label="备注" min-width="260">
          <template #default="scope">
            <div class="remark-cell">
              <el-input
                v-model="remarkDraftMap[scope.row.id]"
                type="textarea"
                :rows="2"
                resize="none"
                placeholder="请输入备注信息"
                @blur="onRemarkBlur(scope.row)"
              />
              <el-button
                class="remark-save-btn"
                :icon="Check"
                circle
                :loading="remarkSavingSet.has(scope.row.id)"
                @click="onRemarkSave(scope.row)"
              />
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-container" style="margin-top: 20px; display: flex; justify-content: flex-end;">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100, 500]"
          background
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>

      <el-drawer v-model="detailVisible" title="资产详情" size="60%">
        <el-card v-if="detailRow" shadow="never" class="detail-card">
          <div class="detail-title">
            <span>{{ detailRow.company || '-' }} / {{ detailRow.ip || '-' }}</span>
          </div>
          <el-collapse v-model="detailCollapsePanels">
            <el-collapse-item name="reason">
              <template #title>
                <span class="reason-title">判断逻辑（reason）</span>
              </template>
              <div class="code-head">
                <el-button size="small" @click="copyText(normalizeAction(detailRow.deepseek_reason))">一键复制</el-button>
              </div>
              <pre class="code-block reason-block">{{ normalizeAction(detailRow.deepseek_reason) }}</pre>
            </el-collapse-item>
            <el-collapse-item name="action">
              <template #title>
                <span>最新建议操作（action）</span>
              </template>
              <div class="code-head">
                <el-button size="small" @click="copyText(normalizeAction(detailRow.deepseek_action))">一键复制</el-button>
              </div>
              <pre class="code-block">{{ normalizeAction(detailRow.deepseek_action) }}</pre>
            </el-collapse-item>
          </el-collapse>
        </el-card>
      </el-drawer>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { Position, Search, Refresh, Check } from '@element-plus/icons-vue'
import {
  fetchClassifiedAssets,
  triggerFullPipeline,
  updateAssetRemark,
  updateAssetStatus
} from '../../api/target'
import type { ClassifiedAssetItem } from '../../types/target'
import { normalizeAction, normalizePriority } from './render-utils'

const form = reactive({
  icp_keyword: '',
  limit: 100
})

const isSubmitting = ref(false)
const loading = ref(false)
const tableData = ref<ClassifiedAssetItem[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(50)
const searchKeyword = ref('')
const remarkDraftMap = reactive<Record<number, string>>({})
const statusUpdatingSet = reactive(new Set<number>())
const remarkSavingSet = reactive(new Set<number>())
const statusClickStampMap = reactive<Record<number, number>>({})
const detailVisible = ref(false)
const detailRow = ref<ClassifiedAssetItem | null>(null)
const detailCollapsePanels = ref<string[]>(['reason', 'action'])
let pollingTimer: number | null = null

const stopPolling = () => {
  if (pollingTimer !== null) {
    window.clearInterval(pollingTimer)
    pollingTimer = null
  }
}

const startPolling = () => {
  stopPolling()
  pollingTimer = window.setInterval(() => {
    fetchData(false)
  }, 10000)
}

const fetchData = async (showLoading = true) => {
  loading.value = true
  try {
    const data = await fetchClassifiedAssets({
      keyword: searchKeyword.value,
      page: currentPage.value,
      size: pageSize.value
    })
    tableData.value = data.list
      .map(item => ({
        ...item,
        deepseek_priority: (item.deepseek_priority ?? '').toString(),
        deepseek_framework: (item.deepseek_framework ?? '').toString(),
        deepseek_reason: (item.deepseek_reason ?? '').toString(),
        deepseek_action: (item.deepseek_action ?? '').toString()
      }))
    total.value = data.total
    for (const row of data.list) {
      remarkDraftMap[row.id] = row.penetration_remark || ''
    }
    if (data.total > 0) {
      stopPolling()
    }
  } catch (error: any) {
    ElMessage.error(error?.message || '网络请求失败')
  } finally {
    if (showLoading) {
      loading.value = false
    } else {
      loading.value = false
    }
  }
}

const onSubmitPipeline = async () => {
  if (!form.icp_keyword.trim()) {
    ElMessage.warning('请输入 ICP 备案主体名称')
    return
  }
  isSubmitting.value = true
  try {
    const msg = await triggerFullPipeline(form)
    ElMessage.success(msg)
    setTimeout(() => {
      fetchData()
      startPolling()
    }, 3000)
  } catch (error: any) {
    ElMessage.error(error?.message || '请求失败')
  } finally {
    isSubmitting.value = false
  }
}

const onMarkPenetrated = async (row: ClassifiedAssetItem) => {
  if (row.penetration_status === 'completed') {
    return
  }
  const now = Date.now()
  const lastClickTs = statusClickStampMap[row.id] || 0
  if (now - lastClickTs < 800 || statusUpdatingSet.has(row.id)) {
    return
  }
  statusClickStampMap[row.id] = now

  statusUpdatingSet.add(row.id)
  try {
    await updateAssetStatus(row.id, true)
    row.penetration_status = 'completed'
    ElMessage.success('状态已更新为已完成')
  } catch (error: any) {
    ElMessage.error(error?.message || '状态更新失败')
  } finally {
    statusUpdatingSet.delete(row.id)
  }
}

const saveRemark = async (row: ClassifiedAssetItem) => {
  if (remarkSavingSet.has(row.id)) {
    return
  }
  const draft = (remarkDraftMap[row.id] ?? '').toString()
  if ((row.penetration_remark || '') === draft) {
    return
  }
  remarkSavingSet.add(row.id)
  try {
    await updateAssetRemark(row.id, draft)
    row.penetration_remark = draft
    ElMessage.success('备注已保存')
  } catch (error: any) {
    remarkDraftMap[row.id] = row.penetration_remark || ''
    ElMessage.error(error?.message || '备注保存失败')
  } finally {
    remarkSavingSet.delete(row.id)
  }
}

const onRemarkBlur = (row: ClassifiedAssetItem) => {
  saveRemark(row)
}

const onRemarkSave = (row: ClassifiedAssetItem) => {
  saveRemark(row)
}

const onCopyUrlAndAction = async (row: ClassifiedAssetItem) => {
  const url = (row.url || '').trim() || '-'
  const action = normalizeAction(row.deepseek_action)
  const actionText = action === '-' ? '' : action.replace(/\[SAFE-POC\]\s*/gi, '').trim()
  const payload = actionText ? `${url} ${actionText}`.trim() : url

  try {
    await navigator.clipboard.writeText(payload)
    ElMessage.success('已复制 URL 与最新操作建议')
  } catch (_e) {
    ElMessage.error('复制失败，请手动复制')
  }
}

const openDetail = (row: ClassifiedAssetItem) => {
  detailRow.value = row
  detailCollapsePanels.value = ['reason', 'action']
  detailVisible.value = true
}

const copyText = async (text: string) => {
  const payload = (text || '').trim()
  if (!payload) {
    ElMessage.warning('无可复制内容')
    return
  }
  try {
    await navigator.clipboard.writeText(payload)
    ElMessage.success('已复制')
  } catch (_e) {
    ElMessage.error('复制失败，请手动复制')
  }
}

const handleSizeChange = (val: number) => {
  pageSize.value = val
  fetchData()
}

const handleCurrentChange = (val: number) => {
  currentPage.value = val
  fetchData()
}

onMounted(() => {
  fetchData()
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<style scoped>
.control-panel {
  margin-bottom: 10px;
}

.status-pending {
  color: #f56c6c;
  font-weight: 600;
}

.status-done {
  color: #67c23a;
  font-weight: 600;
}

.remark-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.remark-save-btn {
  flex-shrink: 0;
}

.action-text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.45;
}

.detail-card {
  border: none;
}

.detail-title {
  margin-bottom: 12px;
  font-weight: 600;
}

.code-head {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
}

.code-block {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 8px;
  padding: 12px;
  line-height: 1.5;
}

.reason-title {
  font-weight: 700;
  color: #2563eb;
}

.reason-block {
  border: 1px solid #2563eb;
}

:deep(.el-tag.priority-p1) {
  background-color: #fee2e2;
  border-color: #fca5a5;
  color: #b91c1c;
}

:deep(.el-tag.priority-p2) {
  background-color: #ffedd5;
  border-color: #fdba74;
  color: #c2410c;
}

:deep(.el-tag.priority-p3) {
  background-color: #dcfce7;
  border-color: #86efac;
  color: #166534;
}

:deep(.el-tag.priority-other) {
  background-color: #e0f2fe;
  border-color: #7dd3fc;
  color: #075985;
}

:deep(.el-tag.priority-empty) {
  background-color: #f3f4f6;
  border-color: #d1d5db;
  color: #6b7280;
}
</style>
