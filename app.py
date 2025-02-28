import streamlit as st
import math
from scipy.optimize import root_scalar

# 页面设置
st.set_page_config(
    page_title="死亡时间推断工具",
    page_icon="⏱️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 标题
st.title("死亡时间推断工具")
st.write('请在侧边栏填写相关信息，然后点击"计算结果"按钮')

# 湿度估算函数（增加雪天情况）
def estimate_humidity(province, month, weather):
    humidity_base = {
        "华南": [70, 70, 70, 80, 80, 80, 65, 65, 65, 60, 60, 60],  # 如广东、广西
        "华东": [65, 65, 65, 75, 75, 75, 60, 60, 60, 55, 55, 55],  # 如上海、江苏
        "华北": [50, 50, 50, 60, 60, 60, 45, 45, 45, 30, 30, 30],  # 如北京、河北
        "西北": [40, 40, 40, 50, 50, 50, 35, 35, 35, 25, 25, 25],  # 如甘肃、新疆
        "东北": [35, 35, 40, 50, 60, 65, 60, 55, 45, 35, 35, 35],  # 如黑龙江、吉林
        "其他": [55, 55, 55, 65, 65, 65, 50, 50, 50, 40, 40, 40]
    }
    # 天气对湿度的影响调整（加入雪天）
    weather_adjust = {
        "晴": -10, 
        "阴": 0, 
        "多云": 5, 
        "小雨": 20, 
        "大雨": 40,
        "小雪": 15, 
        "大雪": 30
    }

    region = "其他"
    if "广东" in province or "广西" in province or "海南" in province:
        region = "华南"
    elif "上海" in province or "江苏" in province or "浙江" in province:
        region = "华东"
    elif "北京" in province or "河北" in province or "山西" in province:
        region = "华北"
    elif "甘肃" in province or "新疆" in province or "青海" in province:
        region = "西北"
    elif "黑龙江" in province or "吉林" in province or "辽宁" in province:
        region = "东北"

    month_index = int(month) - 1
    base_humidity = humidity_base[region][month_index]
    adjust = weather_adjust.get(weather, 0)
    estimated_humidity = base_humidity + adjust
    return max(0, min(100, estimated_humidity))

# 死亡时间推断函数（含双指数模型和核对，提供多个概率区间）
def estimate_death_time(height, body_type, sex, age, env_temp, clothing, 
                       rectal_temp=None, rigor_mortis=None, livor_mortis=None, livor_pressure=None):
    all_estimates = []
    threshold = 12  # 差异阈值，超过此值认为尸僵/尸斑不准确
    warning_messages = []
    
    # 默认湿度估算
    humidity = estimate_humidity("其他", 6, "阴")

    # 尸温推断（双指数模型）
    temp_estimate = None
    if rectal_temp is not None:
        normal_temp = 37.0
        clothing_correction = {1: 1.2, 2: 1.1, 3: 1.0, 4: 0.9, 5: 0.8}
        body_type_correction = {1: 1.2, 2: 1.0, 3: 0.9, 4: 0.8}
        sex_correction = {1: 1.0, 2: 0.95}
        age_correction = 1.1 if age < 18 or age > 60 else 1.0
        c = (clothing_correction.get(clothing, 1.0) * body_type_correction.get(body_type, 1.0) * 
             sex_correction.get(sex, 1.0) * age_correction)
        
        # 由于删除了湿度、风速和水中选项，保留默认行为即可
        if humidity > 70:
            c *= 0.95
            
        k1, k2, t_plateau = 0.05, 0.02, 4
        def equation(t):
            if t <= t_plateau:
                return normal_temp - (normal_temp - env_temp) * (1 - math.exp(-k1 * c * t)) - rectal_temp
            else:
                return normal_temp - (normal_temp - env_temp) * ((1 - math.exp(-k1 * c * t_plateau)) * math.exp(-k2 * c * (t - t_plateau))) - rectal_temp
        
        # 检查温差，只有在真正温差小时才显示特定警告
        temp_diff = rectal_temp - env_temp
        
        try:
            sol = root_scalar(equation, bracket=[0, 120], method='brentq')
            hours = sol.root
            uncertainty = max(2, hours * 0.4) if temp_diff < 2 else max(1, hours * 0.2)
            temp_estimate = (max(0, hours - uncertainty), hours + uncertainty)
            all_estimates.append(temp_estimate)
            
            # 只有在温差确实小于2度时才显示温差过小警告
            if temp_diff < 2:
                warning_messages.append(f"尸温与环境温度差异过小（{temp_diff:.1f}℃），估计结果可能不准确。")
                
        except ValueError:
            all_estimates.append((0, 8))
            if temp_diff < 5:
                warning_messages.append("尸温计算出现问题，可能是温度差异不足导致。")

    # 尸僵推断
    rigor_estimate = None
    if rigor_mortis is not None:
        base_ranges = {0: (0, 3), 1: (2, 6), 2: (4, 10), 3: (8, 20), 4: (16, 36), 5: (24, 48), 6: (36, 72)}
        rigor_estimate = base_ranges.get(rigor_mortis, (0, 3))
        all_estimates.append(rigor_estimate)

    # 尸斑推断
    livor_estimate = None
    if livor_mortis is not None and livor_pressure is not None:
        livor_ranges = {0: (0, 0.5), 1: (0.5, 4), 2: (2, 8), 3: (6, 16), 4: (12, 36), 5: (24, 48)}
        pressure_ranges = {0: (0, 6), 1: (2, 10), 2: (6, 16), 3: (12, 24), 4: (16, 48)}
        lower = max(livor_ranges.get(livor_mortis, (0, 0.5))[0], pressure_ranges.get(livor_pressure, (0, 6))[0])
        upper = min(livor_ranges.get(livor_mortis, (0, 0.5))[1], pressure_ranges.get(livor_pressure, (0, 6))[1])
        livor_estimate = (lower, upper)
        all_estimates.append(livor_estimate)

    # 核对逻辑：如果有尸温结果，检查尸僵/尸斑是否合理
    if temp_estimate and (rigor_estimate or livor_estimate):
        temp_lower, temp_upper = temp_estimate
        temp_mid = (temp_lower + temp_upper) / 2  # 尸温的中值
        
        if rigor_estimate:
            rigor_lower, rigor_upper = rigor_estimate
            rigor_mid = (rigor_lower + rigor_upper) / 2
            if abs(rigor_mid - temp_mid) > threshold:  # 差异超过12小时
                all_estimates = [temp_estimate]  # 只用尸温
                warning_messages.append("尸僵数据可能不准确，已优先使用尸温结果！")
        
        if livor_estimate:
            livor_lower, livor_upper = livor_estimate
            livor_mid = (livor_lower + livor_upper) / 2
            if abs(livor_mid - temp_mid) > threshold:
                all_estimates = [temp_estimate]  # 只用尸温
                warning_messages.append("尸斑数据可能不准确，已优先使用尸温结果！")

    # 综合估计 - 提供多概率区间
    if all_estimates:
        lower_bounds = [est[0] for est in all_estimates]
        upper_bounds = [est[1] for est in all_estimates]
        
        # 基础计算
        final_lower = sum(lower_bounds) / len(lower_bounds)
        final_upper = sum(upper_bounds) / len(upper_bounds)
        mid_point = (final_lower + final_upper) / 2
        full_range = (final_lower, final_upper)
        
        # 每种方法的权重分配
        weights = {}
        if rectal_temp is not None:
            weights["temp"] = 0.8  # 尸温通常更精确
            if (rectal_temp - env_temp) < 2:
                weights["temp"] = 0.6  # 温差小时可靠性降低
        if rigor_mortis is not None:
            weights["rigor"] = 0.6
        if livor_mortis is not None and livor_pressure is not None:
            weights["livor"] = 0.7
        
        # 计算加权平均和标准差
        if weights:
            weighted_values = []
            weight_sum = 0
            for i, (low, high) in enumerate(all_estimates):
                method = ["temp", "rigor", "livor"][min(i, 2)]
                if method in weights:
                    mid = (low + high) / 2
                    weighted_values.append((mid, weights[method]))
                    weight_sum += weights[method]
            
            if weight_sum > 0:
                # 计算加权中点
                weighted_mid = sum(val * w for val, w in weighted_values) / weight_sum
                
                # 计算加权标准差
                variance = sum(w * ((val - weighted_mid) ** 2) for val, w in weighted_values) / weight_sum
                std_dev = (variance ** 0.5) if variance > 0 else (final_upper - final_lower) / 4
                
                # 计算概率区间
                range_90 = (max(0, weighted_mid - 1.645 * std_dev), 
                           weighted_mid + 1.645 * std_dev)  # 90% 置信区间
                range_70 = (max(0, weighted_mid - 1.036 * std_dev), 
                           weighted_mid + 1.036 * std_dev)  # 70% 置信区间
                range_50 = (max(0, weighted_mid - 0.675 * std_dev), 
                           weighted_mid + 0.675 * std_dev)  # 50% 置信区间
                
                return {
                    "full_range": full_range,
                    "range_90": range_90,
                    "range_70": range_70,
                    "range_50": range_50,
                    "warnings": warning_messages,
                    "best_estimate": weighted_mid
                }
        
        # 如果没有权重信息，使用简单估计
        std_dev = (final_upper - final_lower) / 4  # 估计标准差
        range_90 = (max(0, mid_point - 1.645 * std_dev), mid_point + 1.645 * std_dev)
        range_70 = (max(0, mid_point - 1.036 * std_dev), mid_point + 1.036 * std_dev)
        range_50 = (max(0, mid_point - 0.675 * std_dev), mid_point + 0.675 * std_dev)
        
        return {
            "full_range": full_range,
            "range_90": range_90,
            "range_70": range_70,
            "range_50": range_50,
            "warnings": warning_messages,
            "best_estimate": mid_point
        }
    
    return {"full_range": (0, 0), "range_90": (0, 0), "range_70": (0, 0), "range_50": (0, 0), 
            "warnings": ["请输入至少一项尸体现象数据！"], "best_estimate": 0}

# 侧边栏输入区域
st.sidebar.header("输入参数")

# 使用选项卡整理表单 - 移除了"关于"选项卡
tab1, tab2, tab3 = st.sidebar.tabs(["基本信息", "环境信息", "尸体现象"])

# 基本信息
with tab1:
    st.write("**基本信息**")
    height = st.number_input("尸体身高 (cm)", min_value=140, max_value=200, value=None, placeholder="输入140-200之间的值", 
                           help="输入身高，140-200 cm，例如 170 cm")
    
    body_type = st.selectbox("体型", options=["", "1-瘦削", "2-正常", "3-超重", "4-肥胖"], 
                           help="选择适合的体型：1-瘦削（骨架明显，少脂肪），2-正常（体重适中），3-超重（稍胖），4-肥胖（明显胖）")
    
    sex = st.radio("性别", options=["1-男性", "2-女性"], horizontal=True,
                 help="选择性别：1-男性，2-女性")
    
    age = st.number_input("年龄 (岁)", min_value=10, max_value=90, value=None, placeholder="输入10-90之间的值",
                        help="输入年龄，10-90岁，例如 30岁")

# 环境信息
with tab2:
    st.write("**环境信息**")
    env_temp = st.number_input("环境温度 (℃)", min_value=-30, max_value=40, value=None, placeholder="输入-30至40之间的值",
                            help="输入温度，-30至40℃，如室内20℃，室外5℃")
    
    clothing = st.selectbox("衣着情况", options=["", "1-几乎无衣物", "2-轻薄", "3-普通", "4-较厚", "5-非常厚重"], 
                          help="选择衣着：1-几乎无衣物（裸露或内衣），2-轻薄（短袖T恤、薄裙），3-普通（衬衫、裤子），4-较厚（毛衣、外套），5-非常厚重（羽绒服、棉衣）")
    
    province = st.text_input("省份", value="", placeholder="如：广东、北京",
                          help="输入省份，如广东、北京，若无匹配用默认值")
    
    month = st.slider("月份", min_value=1, max_value=12, value=None, 
                    help="输入月份，1-12，如7表示7月")
    
    weather = st.selectbox("天气", options=["", "晴", "阴", "多云", "小雨", "大雨", "小雪", "大雪"], 
                         help="选择天气：晴、阴、多云、小雨、大雨、小雪、大雪")

# 尸体现象
with tab3:
    st.write("**尸温与尸僵**")
    rectal_temp = st.number_input("直肠温度 (℃, 可选)", min_value=0.0, max_value=40.0, value=None, placeholder="输入测量温度", 
                                help="正常体温37℃，如30℃表示降温，低于环境温度无效")
    
    rigor_mortis = st.selectbox("尸僵程度 (可选)", 
                             options=["", "0-无", "1-颌部颈部", "2-四肢部分", "3-全身可变", "4-全身强直", "5-开始缓解", "6-大部分缓解"],
                             help="选择尸僵：0-无僵硬，1-仅颌部颈部硬（如咬紧牙关），2-四肢部分硬（如手臂难弯），3-全身硬但可掰动，4-全身强直（如硬如木板），5-开始变软（如手指可动），6-大部分变软（仅少处硬）")
    
    st.write("**尸斑**")
    livor_mortis = st.selectbox("尸斑程度 (可选)", 
                             options=["", "0-无", "1-散在点状", "2-融合浅", "3-大片深色", "4-深暗皮革", "5-消退模糊"],
                             help="选择尸斑：0-无尸斑，1-散在点状（如小红点），2-融合浅色（如淡红片），3-大片深色（如紫红），4-深暗皮革样（如暗紫硬化），5-消退模糊（如边缘变浅）")
    
    livor_pressure = st.selectbox("尸斑压迫反应 (可选)", 
                               options=["", "0-完全消失", "1-大部分变浅", "2-部分变浅", "3-轻微变浅", "4-无变化"],
                               help="选择尸斑压迫：0-指压完全消失，1-指压大部分变浅（如仍见轮廓），2-指压部分变浅（如稍淡），3-指压轻微变浅（如几乎不变），4-指压无变化")

# 获取值函数
def get_value(value, type_):
    if type_ == "selectbox":
        if value and value != "":
            return int(value.split("-")[0])
        return None
    elif type_ == "radio":
        return int(value.split("-")[0])
    return value

# 计算按钮
if st.button("计算结果", type="primary"):
    try:
        # 检查必填项
        if not height or not body_type or not age or not env_temp or not clothing or not province or not month or not weather:
            st.error("请填写所有基本信息和环境信息！")
        else:
            # 处理输入
            height_val = float(height)
            body_type_val = get_value(body_type, "selectbox")
            sex_val = get_value(sex, "radio")
            age_val = int(age)
            env_temp_val = float(env_temp)
            clothing_val = get_value(clothing, "selectbox")
            month_val = int(month)
            
            # 处理可选值
            rectal_temp_val = float(rectal_temp) if rectal_temp else None
            rigor_mortis_val = get_value(rigor_mortis, "selectbox") if rigor_mortis else None
            livor_mortis_val = get_value(livor_mortis, "selectbox") if livor_mortis else None
            livor_pressure_val = get_value(livor_pressure, "selectbox") if livor_pressure else None
            
            # 计算结果
            time_ranges = estimate_death_time(
                height_val, body_type_val, sex_val, age_val, env_temp_val, clothing_val, 
                rectal_temp_val, rigor_mortis_val, livor_mortis_val, livor_pressure_val
            )
            
            # 显示警告
            for warning in time_ranges["warnings"]:
                st.warning(warning)
            
            # 显示结果
            if time_ranges["full_range"] != (0, 0):
                st.subheader("死亡时间推断结果")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("整体范围 (小时)", f"{time_ranges['full_range'][0]:.1f} - {time_ranges['full_range'][1]:.1f}")
                    st.metric("70%概率区间 (小时)", f"{time_ranges['range_70'][0]:.1f} - {time_ranges['range_70'][1]:.1f}")
                
                with col2:
                    st.metric("90%概率区间 (小时)", f"{time_ranges['range_90'][0]:.1f} - {time_ranges['range_90'][1]:.1f}")
                    st.metric("50%概率区间 (小时)", f"{time_ranges['range_50'][0]:.1f} - {time_ranges['range_50'][1]:.1f}")
                
                # 使用最可能的估计值，不显示具体日期时间
                best_estimate = time_ranges['best_estimate']
                
                st.success(f"**最可能的死亡时间范围**: 即 **{best_estimate:.1f}小时** 之前")
                
                # 在结果下方添加简化的信息和免责声明
                st.info("""
                **免责声明**：本工具仅供专业参考使用，实际案件应由具备资质的法医人员根据全面现场调查与尸检结果做出综合判断。
                开发者不对使用结果承担相关法律责任。
                """)
                
                # 使用expander收纳更多信息
                with st.expander("关于此工具"):
                    st.markdown("""
                    **工具原理**：基于双指数冷却方程（Henssge模型改良版）推断死亡时间，并结合尸僵发展过程和尸斑形成固定等特征，
                    通过加权计算提供多种置信区间。计算过程考虑体型、衣物、性别、年龄等修正系数。
                    
                    **开发者**：王起  南方医科大学
                    """)

    except Exception as e:
        st.error(f"计算出错: {str(e)}，请检查输入！")