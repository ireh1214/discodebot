import os
from dotenv import load_dotenv
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta, timezone
import re
import asyncio
import random


# env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# discord
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)



KST = timezone(timedelta(hours=9))

def parse_flexible_time(input_str: str) -> datetime | None:
    parts = re.findall(r'\d+', input_str)
    if len(parts) < 2:
        return None

    try:
        year = datetime.now().year
        month = int(parts[0])
        day = int(parts[1])
        hour = int(parts[2]) if len(parts) >= 3 else 0
        dt_kst = datetime(year, month, day, hour, tzinfo=KST)
        return dt_kst
    except Exception:
        return None




class RoleButton(discord.ui.Button):
    ROLE_COLORS = {
        "딜러": discord.ButtonStyle.danger,  # 빨간색
        "세가": discord.ButtonStyle.primary, # 파란색 
        "세바": discord.ButtonStyle.success  # 초록색 
    }

    def __init__(self, role_name: str, view: "PartyView"):
        style = self.ROLE_COLORS.get(role_name, discord.ButtonStyle.secondary)
        super().__init__(label=role_name, style=style)
        self.role_name = role_name
        self.view_obj = view

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user

        # 중복 역할 체크
        for role, users in self.view_obj.participants.items():
            if user in users and role != self.role_name:
                await interaction.response.send_message(
                    f"❌ 이미 `{role}` 역할로 참가 중입니다!", ephemeral=True
                )
                return

        # 토글 기능 (참가/취소)
        if user in self.view_obj.participants[self.role_name]:
            self.view_obj.participants[self.role_name].remove(user)
        else:
            self.view_obj.participants[self.role_name].append(user)

        await interaction.response.edit_message(embed=self.view_obj.generate_embed(), view=self.view_obj)


class PartyView(discord.ui.View):
    def __init__(self, dungeon: str, time: str, note: str):
        super().__init__(timeout=None)
        self.dungeon = dungeon
        self.time = time
        self.note = note

        self.participants = {
            "딜러": [],
            "세가": [],
            "세바": []
        }

        # 역할 버튼들은 0행(row=0)으로 지정
        for role in self.participants.keys():
            button = RoleButton(role, self)
            button.row = 0
            self.add_item(button)

        # 완료 버튼은 1행(row=1)으로 지정해서 아래쪽에 배치
        complete_btn = CompleteButton(self)
        complete_btn.row = 1
        self.add_item(complete_btn)
        

    def generate_embed(self):
        embed = discord.Embed(
            title=f"{self.dungeon}",
            description=f"**시간**: {self.time}\n **내용**: {self.note}",
            color=discord.Color.blue()
        )

        for role, users in self.participants.items():
            if users:
                value = "\n".join(user.mention for user in users)
            else:
                value = ""
            embed.add_field(name=f"{role} ({len(users)})", value=value, inline=True)

        return embed


@bot.tree.command(name="파티생성", description="파티 모집 메시지를 생성합니다.")
@app_commands.describe(
    dungeon="던전 이름을 입력하세요.",
    time="시작 시간을 입력하세요.(24시간제로) 예: 7-15-9시, 7.15 09:00",
    note="파티 모집 내용을 입력하세요."
)
@app_commands.rename(dungeon="던전", time="시간", note="내용")
async def create_party(
    interaction: discord.Interaction,
    dungeon: str,
    time: str,
    note: str
):
    dt_kst = parse_flexible_time(time)
    if not dt_kst:
        await interaction.response.send_message("시간 형식이 올바르지 않습니다. 예: 7-15-9시", ephemeral=True)
        return
    
    formatted_time = dt_kst.strftime("%Y-%m-%d %H:%M")
    view = PartyView(dungeon, formatted_time, note)
    embed = view.generate_embed()

    await interaction.response.send_message(embed=embed, view=view)
    message = await interaction.original_response()

    # 스레드 생성
    thread = await message.create_thread(name=f"{dungeon}", auto_archive_duration=60)
# 

@bot.event
async def on_ready():
    print(f"✅ 봇 로그인 완료: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🌐 슬래시 커맨드 동기화 완료 ({len(synced)}개)")
    except Exception as e:
        print(f"❌ 슬래시 커맨드 동기화 실패: {e}")
        
        

class DistributionView(discord.ui.View):
    def __init__(self, member_buttons):
        super().__init__(timeout=None)
        for button in member_buttons:
            self.add_item(button)

class CompleteButton(discord.ui.Button):
    def __init__(self, view_obj):
        super().__init__(label="파티 모집 완료", style=discord.ButtonStyle.secondary)
        self.view_obj = view_obj

    async def callback(self, interaction: discord.Interaction):
        try:
            dt_kst = datetime.strptime(self.view_obj.time, "%Y-%m-%d %H:%M").replace(tzinfo=KST)
            event_time_utc = dt_kst.astimezone(timezone.utc)
        except Exception:
            await interaction.response.send_message("시간 형식이 올바르지 않습니다.", ephemeral=True)
            return

        guild = interaction.guild
        event = await guild.create_scheduled_event(
            name=f"{self.view_obj.dungeon} 파티 모집",
            start_time=event_time_utc,
            end_time=event_time_utc + timedelta(hours=2),
            description=f"파티 내용: {self.view_obj.note}",
            privacy_level=discord.PrivacyLevel.guild_only,
            entity_type=discord.EntityType.external,
            location="디스코드 파티 모집"
        )

        await interaction.response.send_message(f"✅ 이벤트 생성 완료: {event.name}", ephemeral=True)

            

class MentionButton(discord.ui.Button):
    def __init__(self, member: discord.Member, author_id: int):
        super().__init__(label=member.display_name, style=discord.ButtonStyle.secondary)
        self.member = member
        self.author_id = author_id
        self.checked = False

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id and interaction.user != self.member:
            await interaction.response.send_message("❌ 이 버튼은 본인 또는 명령어 실행자만 누를 수 있어요!", ephemeral=True)
            return

        self.checked = not self.checked
        if self.checked:
            self.style = discord.ButtonStyle.success
            if not self.label.endswith(" ✅"):
                self.label += " ✅"
        else:
            self.style = discord.ButtonStyle.secondary
            self.label = self.label.replace(" ✅", "")

        await interaction.response.edit_message(view=self.view)

        all_checked = all(
            getattr(button, 'checked', False)
            for button in self.view.children
            if isinstance(button, MentionButton) or isinstance(button, TextNameButton)
        )
        if all_checked:
            await interaction.followup.send("🎉 모두에게 분배금이 지급 완료되었습니다!", ephemeral=True)

class TextNameButton(discord.ui.Button):
    def __init__(self, name: str, author_id: int):
        super().__init__(label=name, style=discord.ButtonStyle.secondary)
        self.name = name
        self.author_id = author_id
        self.checked = False

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ 이 버튼은 명령어 실행자만 누를 수 있어요!", ephemeral=True)
            return

        self.checked = not self.checked
        if self.checked:
            self.style = discord.ButtonStyle.success
            if not self.label.endswith(" ✅"):
                self.label += " ✅"
        else:
            self.style = discord.ButtonStyle.secondary
            self.label = self.label.replace(" ✅", "")

        await interaction.response.edit_message(view=self.view)

        all_checked = all(
            getattr(button, 'checked', False)
            for button in self.view.children
            if isinstance(button, MentionButton) or isinstance(button, TextNameButton)
        )
        if all_checked:
            await interaction.followup.send("🎉 모두에게 분배금이 지급 완료되었습니다!", ephemeral=True)

@bot.command()
async def 쓰는법(ctx):
    help_text = """
📌 **사용 가능한 명령어 안내**

### 🐾 슬래시 명령어 (`/` 로 사용)
- `/파티생성`: 역할별 참가 버튼이 포함된 파티 모집 메시지를 생성합니다.
    - 던전 / 시간 / 내용 입력 가능 (예: 7-15-9시)
- `/성수분배`: 성수 판매 수익을 자동 계산합니다.
    - 성수 개수 / 판매 금액 / 인원수 / 수수료 할인율 입력 가능
-
### 🐾 느낌표 명령어 (`!` 로 사용)
- `!차렷` → 퍼리가 인사해줍니다 🐾  
- `!분배시작 [@이름1 이름2 ...]` → 분배 체크 버튼 생성  
- `!단순분배 [총금액] [인원수=8] [제작비=0]` → 기본 분배 계산  
- `!성수분배 [개수] [가격] [인원수=8] [수수료할인=0]` → 슬래시 명령어가 더 정확하고 편해요!
- `!랜덤 항목1 항목2 ...` → 무작위 항목 선택  
- `!채널점지` → 채널 무작위 추천 + 버튼 재추첨 가능 🎯  
    """
    await ctx.send(help_text)

@bot.command()
async def 차렷(ctx):
    greetings = [
        "안녕하세여!",
        "안녕하세여!",
        "안녕하세여!",
        "안녕하세여!",
        "출석했습니다! 🐾",
        "적게 일하고 많이 버시길!",
        "아... 자꾸 부르네...",
        "차렷!!!!!!!!!!!!!! ㅇㅂㅇ",
        "오늘도 정수 코어 드시길 주인님들!",
    ]
    await ctx.send(random.choice(greetings))

@bot.command()
async def 랜덤(ctx, *choices):
    if not choices:
        await ctx.send("❌ 선택할 항목을 입력해 주세요. 예: `!랜덤 차숙희 공홍 안세린 사늑`")
        return

    selected = random.choice(choices)
    message = f"🎲 랜덤 선택 결과는?: \n# {selected} 🎉"
    await ctx.send(message)

@bot.command()
async def 분배시작(ctx, *args):
    if not args:
        await ctx.send("👥 파티원 이름 또는 멘션을 입력해 주세요. 예: `!분배시작 @루니클 @차숙희 @공홍`")
        return

    member_buttons = []
    for arg in args:
        if arg.startswith("<@") and arg.endswith(">"):
            member_id = int(arg.strip("<@!>"))
            member = ctx.guild.get_member(member_id)
            if member:
                member_buttons.append(MentionButton(member, author_id=ctx.author.id))
        else:
            name = arg
            member_buttons.append(TextNameButton(name, author_id=ctx.author.id))

    view = DistributionView(member_buttons)
    message = random.choice([
        "분배금 수령리스트입니다~ 바쁘다 바빠!",
        "이번 분배금 받으실 분들 목록입니다! 'w'",
        "분배금 수령자 리스트입니다! 총대는 수고해줘!",
        "누가누가 분배금 받나 볼까?"
    ])
    await ctx.send(message, view=view)

def parse_price(raw):
    if isinstance(raw, str) and '숲' in raw:
        number = re.sub(r'[^0-9]', '', raw)
        return int(number) * 10000
    raw = str(raw)
    if raw.isdigit() and len(raw) < 7:
        return int(raw) * 10000
    return int(raw)

def parse_cost_input(raw):
    if isinstance(raw, str) and '숲' in raw:
        number = re.sub(r'[^0-9]', '', raw)
        return int(number) * 10000
    return int(raw)

@bot.command()
async def 단순분배(ctx, total_price_raw, members: int = 8, cost_raw: str = "0"):
    total_price = parse_price(total_price_raw)
    try:
        total_cost = parse_cost_input(cost_raw)
    except ValueError:
        await ctx.send("❌ 제작비는 숫자 또는 숲 단위로 입력해 주세요. 예: `80`, `80숲`, `800000`")
        return

    net_profit = total_price - total_cost
    if net_profit < 0:
        await ctx.send("❌ 손해입니다! 총 판매가에서 제작비를 뺀 값이 음수예요.")
        return

    per_person = net_profit // members
    total_forest = total_price // 10000
    per_person_forest = per_person // 10000

    if total_cost == 0:
        cost_text = "제작비는 성수가 아니라 따로 없음!"
    else:
        cost_text = f"제작비는 **{total_cost // 10000}숲 ({total_cost:,}원)**입니당!"

    message = (
        f"분배금 계산 완료!\n\n"
        f"총 **{members}명**의 파티원이 약 **{total_forest}숲** ({total_price:,})의 금액을 분배합니다.\n"
        f"💸 남은 수익: **{net_profit:,}원**\n"
        f"👤 1인당 분배금: **{per_person:,}원** (= 약 {per_person_forest}숲, **1숲 단위 절사**)\n\n"
        f"{cost_text}"
    )
    await ctx.send(message)

# 내부 점지 로직 함수
async def 채널점지_실행(ctx=None, interaction=None, author_id=None):
    excluded_channels = [11, 19]
    field_raid_channels = [12, 13, 14, 15]
    available_channels = [i for i in range(1, 43) if i not in excluded_channels]
    selected_channel = random.choice(available_channels)

    flavor_texts = [
        "득템 한번 가보자고!",
        "원트원클 시원하게 갑시다!",
        "오늘은 과연 어떤 일이 일어날까?",
        "사고 없이 무탈하게 다녀오시죠 주인님들 'w'",
    ]
    extra_text = random.choice(flavor_texts)
    typing_sequence = ["🐾 점지 중.", "🐾 점지 중..", "🐾 점지 중..."]

    target = ctx if ctx else interaction
    msg = await target.send(typing_sequence[0])
    for _ in range(3):
        for text in typing_sequence:
            await asyncio.sleep(0.4)
            await msg.edit(content=text)
    await asyncio.sleep(1)

    if selected_channel == 2:
        description = f"🎯 **{selected_channel}채널**이 선정되었습니다!\n⚠️ 이 채널은 생산 채널이네요! 다시 뽑기 가능!"
        view = RetryChannelView(author_id)
    elif selected_channel in field_raid_channels:
        description = f"🎯 **{selected_channel}채널**이 선정되었습니다!\n⚠️ 필드 레이드 채널입니다! 다시 뽑기 가능!"
        view = RetryChannelView(author_id)
    else:
        description = f"🎯 **{selected_channel}채널**이 선정되었습니다!\n{extra_text}"
        view = None

    await msg.edit(content=description, view=view)

# 명령어 호출
@bot.command()
async def 채널점지(ctx):
    await 채널점지_실행(ctx=ctx, author_id=ctx.author.id)

# 버튼 뷰
class RetryChannelView(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=30)
        self.author_id = author_id

    @discord.ui.button(label="🔄 다시 뽑기", style=discord.ButtonStyle.primary)
    async def retry(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ 이 버튼은 명령어 실행자만 사용할 수 있어요!", ephemeral=True)
            return

        await interaction.response.defer()
        await 채널점지_실행(interaction=interaction, author_id=self.author_id)




@bot.tree.command(name="성수분배", description="성수 판매 분배금을 계산합니다.")
@app_commands.describe(
    count="성수 개수를 숫자로 적어주세요 (예: 8)",
    raw_price="성수 가격 (185숲,  1,850,000,  185)",
    members="파티 인원 수 (기본: 8명)",
    fee_discount="경매장 수수료 할인율 % (기본: 0%)"
)
@app_commands.rename(
    count="성수개수",
    raw_price="판매금액",
    members="인원수",
    fee_discount="수수료몇퍼"
)
async def 성수분배(
    interaction: discord.Interaction,
    count: int,
    raw_price: str,
    members: int = 8,
    fee_discount: int = 0
):
    
    titles = [
    "이번 성수 분배 결과입니다 주인님!",
    "다녀오시느라 고생 많으셨습니다!",
    "어디보자~ 성수 수익 계산 완료입니다!",
    "이번 자 성수 분배는?",
    "컥 귀찮지만 해냄"
    ]
    
    import datetime
    today = datetime.datetime.today().weekday()

    try:
        price = parse_price(raw_price)
    except Exception:
        await interaction.response.send_message("❌ 성수 가격 형식이 잘못되었습니다. 예: `100`, `100숲`, `1000000`", ephemeral=True)
        return

    base_fee_rate = 0.04
    fee_rate = base_fee_rate * (1 - (fee_discount / 100))
    total_sale = price * count
    fee = int(total_sale * fee_rate)

    cost_per_unit = 760000 if today == 2 else 800000
    total_cost = cost_per_unit * count
    net_profit = total_sale - total_cost - fee

    if net_profit < 0:
        await interaction.response.send_message("❌ 손해입니다. 제작비와 수수료를 고려한 수익이 적자입니다!", ephemeral=True)
        return

    per_person = net_profit // members
    weekday_text = "📉 수요일 할인 적용 (76만)" if today == 2 else "📈 기본 제작비 (80만)"

    # 💡 임베드 미리보기 메시지
    embed = discord.Embed(
        title=random.choice(titles),
        color=discord.Color.green()
    )
    embed.add_field(name="성수 개수", value=f"{count}개", inline=True)
    embed.add_field(name="개당 가격", value=f"{price:,}원", inline=True)
    embed.add_field(name="총 판매금액", value=f"{total_sale:,}원", inline=True)
    embed.add_field(name="총 제작비", value=f"{total_cost:,}원", inline=True)
    embed.add_field(name="수수료", value=f"{fee:,}원", inline=True)
    embed.add_field(name="최종 수익", value=f"{net_profit:,}원", inline=True)
    embed.add_field(name="인원 수", value=f"{members}명", inline=True)
    embed.add_field(name="1인당 분배금", value=f"{per_person:,}원", inline=False)
    embed.set_footer(text=weekday_text)


    await interaction.response.send_message(embed=embed)


bot.run(TOKEN)