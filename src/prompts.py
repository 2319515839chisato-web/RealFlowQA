# prompts.py
# For the structure-enhanced experiment:
# 1. Flowchart image -> Figure2StructuralText
# 2. Flowchart image + Figure2StructuralText + question -> answer
#
# Current Figure2StructuralText schema:
# - The top level retains only chart_id, title, lanes, nodes, and edges.
# - lanes represent swimlanes or responsibility regions; when no swimlane exists, lanes = [].
# - nodes retain only node_id, text, full_label, lane_id, and responsible.
# - edges retain only edge_id, from, to, condition, edge_type, and description.
# - loop_edges, uncertain_nodes, uncertain_edges, notes, related_documents, and paths are not included.

from textwrap import dedent


def build_structure_prompt(chart_id: str = "") -> str:
    """
    Stage 1:
    Parse the flowchart image into Figure2StructuralText.

    The final JSON output is allowed to contain only:
    chart_id, title, lanes, nodes, and edges.
    """

    return dedent(f"""
    你是一名流程图结构解析专家。请读取给定流程图图片，并将其转换为 Figure2StructuralText 结构化文本。

    当前流程图编号：
    {chart_id}

    你的任务不是概括流程图内容，而是准确恢复流程图中的：
    1. 泳道或责任区域；
    2. 流程执行节点；
    3. 节点之间的箭头方向；
    4. 条件分支；
    5. 返工、回退或循环路径。

    ====================
    一、最高优先级规则
    ====================

    1. 必须以图中可见文字和箭头方向为准，不能根据业务常识自行改写。
    2. 节点文字必须尽量保留图中原文。
    3. “审批”“审核”“审阅”“审查”“复核”等动作词不能混用。
    4. 本结构中不单独输出 type 和 audit_action，但如果节点文字是“审批”“审核”“审阅”等动作，必须通过 full_label 表达完整语义。
       例如：
       - 总经理泳道中的“审批”节点，text 写“审批”，full_label 写“总经理审批”。
       - 财务部泳道中的“审核”节点，text 写“审核”，full_label 写“财务部审核”。
       - 领导泳道中的“审阅”节点，text 写“审阅”，full_label 写“领导审阅”。
    5. 箭头方向必须根据箭头头部判断。箭头头部指向哪里，to 就是哪里。
    6. 不允许因为业务顺序看起来合理，就反向改写箭头。
    7. 不要输出 related_documents。
    8. 不要输出 paths。
    9. 不要输出 loop_edges。
    10. 不要输出 uncertain_nodes。
    11. 不要输出 uncertain_edges。
    12. 不要输出 notes。
    13. 不与任何流程边相连、且仅作为制度、表单、报告、合同、清单、记录、法规、档案等说明性内容出现的对象，不要作为 nodes。
    14. 如果图中没有泳道或责任区域，lanes 必须输出 []，不要为了“序号”“节点”等编号列创建泳道。

    ====================
    二、lanes：泳道或责任区域
    ====================

    - 识别流程图中的泳道、部门、岗位、角色或责任区域。
    - 例如：总经理、财务部、采购经理、采购员、行政部、相关部门、各部门、安全委员会等。
    - 如果图中存在“相关规程/表单/档案/记录/报告/制度/合同/清单/法规”等列，可以作为 lane 记录。
    - 这类列不是执行主体时，description 必须写“非执行泳道”。
    - lane_id 使用 L1、L2、L3 等编号。
    - 如果原图没有泳道，lanes 必须为 []。
    - 不要把“序号”“节点”等编号列识别为泳道。

    lanes 字段格式：
    {{
      "lane_id": "L1",
      "name": "总经理",
      "description": "执行泳道"
    }}

    ====================
    三、nodes：流程执行节点
    ====================

    nodes 只记录流程执行节点，不记录孤立的相关文件、表单、制度、记录、报告、合同、清单等。

    每个节点只包含以下字段：
    - node_id
    - text
    - full_label
    - lane_id
    - responsible

    不允许输出：
    - type
    - audit_action
    - bbox
    - confidence

    字段规则：

    1. node_id：
       - 使用 N1、N2、N3 等编号。
       - 节点编号尽量按照流程图箭头执行顺序排列，而不是简单按版面从左到右或从上到下排列。
       - 如果存在分支或回路，先编号主流程，再编号分支和回路中尚未编号的节点。
       - 如果流程有多个入口，按主要入口优先编号。

    2. text：
       - 必须尽量保留图中节点原始文字。
       - 不要把“审批”改成“审核”。
       - 不要把“审核”改成“审批”。
       - 不要把“审阅”改成“审核”。
       - 不要把“月底清点”改成“月度清点”，除非图中文字确实如此。
       - 对于审批/审核/审阅节点，text 保留图中原文字，如“审批”“审核”“审阅”，不要擅自加责任主体。

    3. full_label：
       - full_label 是责任主体 + 节点文本。
       - 例如：
         text = "审批"，responsible = "总经理"，full_label = "总经理审批"。
         text = "审核"，responsible = "财务部"，full_label = "财务部审核"。
         text = "执行采购"，responsible = "采购员"，full_label = "采购员执行采购"。
       - 如果 text 本身已经包含责任主体，不要重复堆叠。
         例如 text 已经是“财务经理审核”，full_label 可以仍写“财务经理审核”。
       - 如果没有泳道或责任主体，full_label 可以等于 text。

    4. lane_id：
       - 填写该节点所在泳道对应的 lane_id。
       - 如果没有泳道，填空字符串 ""。

    5. responsible：
       - 根据节点所在泳道或责任区域填写。
       - 如果没有泳道或无法判断责任主体，填空字符串 ""。

    ====================
    四、edges：流程执行边
    ====================

    edges 只记录真实流程箭头。
    返工、回退、循环路径也记录在 edges 中，并用 edge_type = "loop" 表示。

    每条边必须包含：
    - edge_id
    - from
    - to
    - condition
    - edge_type
    - description

    字段规则：

    1. from 和 to：
       - from 和 to 使用 node_id。
       - from 是箭头起点，to 是箭头终点。
       - 必须根据箭头头部判断方向。
       - 如果箭头方向看不清，不要强行写入 edges。

    2. condition：
       - 如果边上有条件标签，写入 condition。
       - 常见条件包括：是、否、Y、N、通过、不通过、合格、不合格、重大、一般、同意、不同意。
       - 图中没有写条件时，condition 必须填空字符串 ""。
       - 不允许写“是（推定）”“否（推定）”“Y（推定）”“N（推定）”。

    3. edge_type：
       - normal：普通流程边；
       - condition：条件分支边；
       - loop：返工、退回、循环路径。
       - 若 condition 非空，一般 edge_type 应为 condition 或 loop。
       - 若是返回上一环节、重新填写、退回审核、返工修改、归还入库等，edge_type 必须为 loop。

    4. description：
       - description 必须使用 from 和 to 对应节点的 text 直接生成。
       - 不允许自行扩写业务描述。
       - 无条件边格式：
         from_text -> to_text
       - 有条件边格式：
         from_text -> to_text，condition=条件值
       - 例如：
         "确定公司经营和预算目标 -> 制订预算编制办法和原则"
         "财务经理审核 -> 总经理审核，condition=Y"
         "总经理审核 -> 财务经理审核，condition=N"
       - description 里不能写 node_id，例如不能写 "N1 -> N2"。
       - description 里必须使用 nodes 中对应 node_id 的 text。

    ====================
    五、最终自检规则
    ====================

    输出 JSON 前必须自行检查：

    1. 顶层字段只能包含：
       chart_id, title, lanes, nodes, edges。
    2. 不允许出现 loop_edges。
    3. 不允许出现 uncertain_nodes。
    4. 不允许出现 uncertain_edges。
    5. 不允许出现 notes。
    6. 不允许出现 related_documents。
    7. 不允许出现 paths。
    8. nodes 中不允许出现 type、audit_action、bbox、confidence。
    9. from 和 to 必须都是 nodes 中存在的 node_id。
    10. description 必须使用 from 和 to 对应节点的 text。
    11. 如果 condition 非空，description 必须包含 condition=条件值。
    12. 不与任何流程边相连的表单、制度、报告、记录等不应进入 nodes。

    ====================
    六、输出要求
    ====================

    1. 只输出 JSON。
    2. 不要输出 Markdown。
    3. 不要输出解释性文字。
    4. 不要使用 ```json 代码块。
    5. JSON 必须能被 Python 的 json.loads() 正常解析。
    6. 如果某个字段无法判断，使用空字符串 "" 或空数组 []。
    7. 不允许省略 chart_id、title、lanes、nodes、edges 字段。

    请严格按照以下 JSON 结构输出：

    {{
      "chart_id": "{chart_id}",
      "title": "",
      "lanes": [
        {{
          "lane_id": "",
          "name": "",
          "description": ""
        }}
      ],
      "nodes": [
        {{
          "node_id": "",
          "text": "",
          "full_label": "",
          "lane_id": "",
          "responsible": ""
        }}
      ],
      "edges": [
        {{
          "edge_id": "",
          "from": "",
          "to": "",
          "condition": "",
          "edge_type": "",
          "description": ""
        }}
      ]
    }}

    现在请根据图片输出 Figure2StructuralText JSON。
    """).strip()
