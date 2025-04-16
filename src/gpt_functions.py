from openai import OpenAI
import os
from typing import List, Dict


def get_chapter_summary(section: Dict, model: str = 'gpt-4o-mini', api_key=os.getenv("OPENAI_API_KEY")) -> str:
    """
    Generates a summary for a given section of a video using the specified OpenAI model.
    Model can convert timedelta to string format. (impressive)
    Args:
        section (dict): The section of the video to summarize.
            keys: 'timestamp' (timedelta), 'heading' (str), content (str)
        model (str, optional): The model to use for generating the summary. Defaults to 'gpt-4o-mini'.
    Returns:
        str: The generated summary of the section.
    """
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {'role': 'system', 
            'content': 
                'Summarize the following section of the video. \
                    Use the provided content to generate a summary of the section. \
                    Stay in the original language. \
                    Explain the content short and conversational as a bullet point. \
                    Do not write things like "They mention the importance" or "the speaker says". \
                    If they talk about the 5 things or the 9 types or something like that, list them. \
                    Answer the question thats given in the topic or chapter title if available. \
                    Put the topic with timestamp (in h, min, sec) [if available] in the format "hh:mm:ss" or "mm:ss" as a heading in the format: "Heading Topic (00:34)"\
                    Every Heading should be a markdown ## heading. If there is no heading title (eg. just Chapter 1), create a heading out of the content provided. \
                    Try to keep it as short as possible, but as long as necessary.'},

            {'role': 'user', 'content': str(section)}
        ],
        temperature=0.08,
        max_tokens=1024,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
        stream=True
    )

    result = ""
    for chunk in response:
        if chunk.choices[0].delta.content is not None:
            result += chunk.choices[0].delta.content

    return result


def get_whole_transcript_summary(transcript: str, api_key=os.getenv("OPENAI_API_KEY")) -> str:
    """
    Generates a summary for the entire transcript. 
    """
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            {'role': 'system', 
            'content': 
                'Summarize the following transcript of a podcast. \
                    Do not only list the topics they talk about, but briefly explain every idea you mention in the summary. \
                    Still try to keep it as short as possible. Use bullet points if possible.'},

            {'role': 'user', 'content': transcript}
        ],
        temperature=0.08,
        max_tokens=1024,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
    )
    result = response.choices[0].message.content
    return result


def get_one_sentence_summary(transcript: str, title="", api_key=os.getenv("OPENAI_API_KEY")) -> str:
    """
    Generates a one-sentence summary for the entire transcript. 
    """
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            {'role': 'system', 
            'content': 
                'Try to summarize the following transcript in EXACTLY ONE SENTENCE. It can be longer if necessary to conserve information.\
                Here is the available title: ' + title + '\n\n Add the title as a markdown #### heading.'},

            {'role': 'user', 'content': transcript}
        ],
        temperature=0.08,
        max_tokens=1024,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
    )
    result = response.choices[0].message.content
    return result


def get_minimal_chapter_summary(api_key: str, section: Dict, model: str = 'gpt-4o-mini') -> str:
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {'role': 'system', 
            'content': 
                'Summarize the following chapter of a podcast as short as possible in max. 1-2 bullet points.\
                    Stay in the original language. Keep the heading.'},

            {'role': 'user', 'content': str(section)}
        ],
        temperature=0.08,
        max_tokens=256,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
    )

    result = response.choices[0].message.content
    return result


def get_unified_summary(api_key: str, sections: List[Dict]) -> str:
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            {'role': 'system', 
            'content': 
                'Summarize the following outline of a podcast. \
                    Do not only list the topics they talk about, but briefly explain every idea you mention in the summary. \
                    Still try to keep it as short as possible. Use bullet points if possible.'},

            {'role': 'user', 'content': str(sections)}
        ],
        temperature=0.08,
        max_tokens=512,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
    )
    
    result = response.choices[0].message.content
    return result


def rework_transcript_to_sentences(transcript_item: dict) -> dict:
    """
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            {'role': 'system', 
            'content': 
                'Rework the following transcript item to a more readable format.\
                Stay in the original language!  \
                Do not change the content, just make it more readable. \
                Shorten this into whole sentences. I want you to build whole sentences with the timestamps, but keep it as short as it makes sense to get a whole and finished sentence. \
                You are allowed to polish that sentence and add punctuation, etc.'},

            {'role': 'user', 'content': str(transcript_item)}
        ],
        temperature=0.1,
        max_tokens=512,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
    )
    result = response.choices[0].message.content
    return result
    

def create_shorts_script(cleaned_transcript: str):
    """
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model='gpt-4o',
        messages=[
            {'role': 'system', 
            'content': 
                'Create a Voiceover for short-form content based on the provided trancript. \
                Stay in the original language and keep it short, engaging and conversational! \
                Create a HOOK at the beginning of the video like "Hast du dich schon mal gefragt, ...?" \
                and a CALL TO ACTION at the end of the video, e.g to check out the full video on the channel. \
                Make it as short as possible! No AI slop or unnecessary words. Absolutely laidback and on point. \
                Create a smooth text without timestamps or block elements to that it can immediately be sythezized to Voice. \
                '},

            {'role': 'user', 'content': cleaned_transcript}
        ],
        temperature=0.1,
        max_tokens=512,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
    )
    result = response.choices[0].message.content
    return result
