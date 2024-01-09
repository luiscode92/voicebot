import logging
import os
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware


from vocode.streaming.models.telephony import TwilioConfig
from pyngrok import ngrok
from vocode.streaming.telephony.config_manager.redis_config_manager import (
    RedisConfigManager,
)
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.telephony.server.base import (
    TwilioInboundCallConfig,
    TelephonyServer,
)

from speller_agent import SpellerAgentFactory
import sys

from vocode.streaming.models.synthesizer import (
  AzureSynthesizerConfig,
  PlayHtSynthesizerConfig,
  ElevenLabsSynthesizerConfig, 
  StreamElementsSynthesizerConfig
)
from vocode.streaming.models.transcriber import DeepgramTranscriberConfig 

from dotenv import load_dotenv
from vocode.streaming.telephony.config_manager.in_memory_config_manager import InMemoryConfigManager

from vocode.streaming.telephony.conversation.outbound_call import OutboundCall
from typing import Optional


load_dotenv()

app = FastAPI(docs_url=None)
templates = Jinja2Templates(directory="view")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You might want to restrict this to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

config_manager = InMemoryConfigManager()

BASE_URL = os.getenv("BASE_URL")

if not BASE_URL:
    ngrok_auth = os.environ.get("NGROK_AUTH_TOKEN")
    if ngrok_auth is not None:
        ngrok.set_auth_token(ngrok_auth)
    port = sys.argv[sys.argv.index("--port") + 1] if "--port" in sys.argv else 3000

    # Open a ngrok tunnel to the dev server
    BASE_URL = ngrok.connect(port).public_url.replace("https://", "")
    logger.info('ngrok tunnel "{}" -> "http://127.0.0.1:{}"'.format(BASE_URL, port))

if not BASE_URL:
    raise ValueError("BASE_URL must be set in environment if not using pyngrok")


# Multilingual support for speech synthesis
# es-CO-SalomeNeural (Female)
# es-CO-GonzaloNeural (Male)
synthesizer_config = AzureSynthesizerConfig(
    voice_name="es-CO-SalomeNeural",
    language_code="es-CO",
    sampling_rate=8000,
    audio_encoding="mulaw"
)

transcriber_config = DeepgramTranscriberConfig(
    language="es",
    sampling_rate=8000,
    audio_encoding="mulaw",
    chunk_size=1000
)

elevenlabs_synthesizer_config=ElevenLabsSynthesizerConfig.from_telephone_output_device(
    api_key=os.getenv("ELEVENLABS_API_KEY")
)

addi_bot_prompt="""You are "Ofelia" a customer service representative calling on behalf of the credit company "Addi." Addi is reaching out regarding a credit account associated with Luis Sanjuan, identified by the credit number 1234, with an outstanding balance of 1000000 de pesos.

Your role is to collect the money by negotiating with the user for the best interest ratio. deliver information and negotiating, aiming to provide a seamless and user-friendly experience for the customer, let customer talk, dont give the whole information at once.

Addi presents the following three options for resolving the outstanding debt:

**Option 1:**
- Duration: 12 months
- Annual Interest Rate: 8%
- Monthly Payment: Approximately 87527 pesos

**Option 2:**
- Duration: 18 months
- Annual Interest Rate: 6%
- Monthly Payment: Approximately 55555 pesos

**Option 3:**
- Duration: 24 months
- Annual Interest Rate: 5%
- Monthly Payment: Approximately 37953 pesos

During the negotiation, showcase Addi's ability to understand and communicate that it is calling on behalf of the credit company. Address Luis Sanjuan by name and reference the specific credit number and outstanding amount. Demonstrate how Addi takes care of its customers, presents the available options, and handles inquiries regarding the repayment plans. Ensure to verify customer data before advancing with the negotiation.

"""


telephony_server = TelephonyServer(
    base_url=BASE_URL,
    config_manager=config_manager,
    inbound_call_configs=[
        TwilioInboundCallConfig(
            url="/inbound_call",
            agent_config=ChatGPTAgentConfig(
                initial_message=BaseMessage(text="Hola, con quien hablo?"),
                prompt_preamble=addi_bot_prompt,
                generate_responses=True,
            ),
            twilio_config=TwilioConfig(
                account_sid=os.environ["TWILIO_ACCOUNT_SID"],
                auth_token=os.environ["TWILIO_AUTH_TOKEN"],
            ),
            synthesizer_config=synthesizer_config,
            transcriber_config=transcriber_config

        )
    ],
    agent_factory=SpellerAgentFactory(),
    logger=logger,
)

app.include_router(telephony_server.get_router())

async def start_outbound_call(to_phone: Optional[str]):
  print("at outbound")
  if to_phone:
      outbound_call = OutboundCall(
        base_url=BASE_URL,
        to_phone=to_phone,
        from_phone="+15202239830",
        config_manager=config_manager,
        synthesizer_config=synthesizer_config,
        transcriber_config=transcriber_config,
        agent_config=ChatGPTAgentConfig(
                initial_message=BaseMessage(text="Hola, con quien hablo?"),
                prompt_preamble=addi_bot_prompt,
                generate_responses=True,
            ),
            twilio_config=TwilioConfig(
                account_sid=os.environ["TWILIO_ACCOUNT_SID"],
                auth_token=os.environ["TWILIO_AUTH_TOKEN"],
            ),
      )

      await outbound_call.start()

# Expose the starter webpage
@app.get("/")
async def root(request: Request):
  env_vars = {
    "BASE_URL": BASE_URL,
    "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
    "DEEPGRAM_API_KEY": os.environ.get("DEEPGRAM_API_KEY"),
    "TWILIO_ACCOUNT_SID": os.environ.get("TWILIO_ACCOUNT_SID"),
    "TWILIO_AUTH_TOKEN": os.environ.get("TWILIO_AUTH_TOKEN"),
    "OUTBOUND_CALLER_NUMBER": os.environ.get("OUTBOUND_CALLER_NUMBER")
  }

  return templates.TemplateResponse("index.html", {
    "request": request,
    "env_vars": env_vars
  })


@app.post("/outbound_call")
async def api_start_outbound_call(to_phone: Optional[str] = Form(None)):
  print(f"Starting outbound call to phone: {to_phone}")
  await start_outbound_call(to_phone)
  return {"status": "success"}
