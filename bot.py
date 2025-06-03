import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
import datetime
import re
import asyncio
import random

# env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# discord
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    print(f"✅ 봇 로그인 완료: {bot.user}")


class DistributionView(discord.ui.View):
    def __init__(self, member_buttons):
        super().__init__(timeout=None)
        for button in member_buttons:
            self.add_item(button)

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
📌 **사용 가능한 명령어 목록**

!차렷 → 퍼리가 인사해줌  
!분배시작 [@이름1 이름2 ...] → 분배 체크 버튼 생성  
!성수분배 [개수] [가격] [인원수=8] [수수료할인=0] → 성수 전용 자동 계산  
!단순분배 [총금액] [인원수 (기본인원 8)] [제작비(따로 안 적으면 없는걸로 침)]
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

@bot.command()
async def 성수분배(ctx, count: int, raw_price, members: int = 8, fee_discount: int = 0):
    today = datetime.datetime.today().weekday()
    price = parse_price(raw_price)

    base_fee_rate = 0.04
    fee_rate = base_fee_rate * (1 - (fee_discount / 100))
    total_sale = price * count
    fee = int(total_sale * fee_rate)

    cost_per_unit = 760000 if today == 2 else 800000
    total_cost = cost_per_unit * count
    net_profit = total_sale - total_cost - fee

    if net_profit < 0:
        await ctx.send("❌ 손해입니다. 제작비와 수수료를 고려한 수익이 적자입니다!")
        return

    per_person = net_profit // members
    weekday_text = "수요일 할인 적용 완료" if today == 2 else "기본가 적용"

    result_message = (
        f"🐾파티원 {members}명의 성수 {count}개 판매 계산 결과입니다!\n\n"
        f"・개당 판매가: **{price:,}원**\n"
        f"・총 제작비: **{total_cost:,}원** ({weekday_text})\n"
        f"・최종 수익: **{net_profit:,}원** (경매장 수수료 {fee:,}원)\n\n"
        f"👥 1인당 분배금: **{per_person:,}원**"
    )

    await ctx.send(result_message)


bot.run(TOKEN)