'use client'
import { useState, useCallback } from 'react';
import parse from 'html-react-parser';

// import './index.css'
const apiHost = process.env.API_HOST || process.env.NEXT_PUBLIC_API_HOST || '';
const username = process.env.USERNAME || process.env.NEXT_PUBLIC_USERNAME;
const password = process.env.PASSWORD || process.env.NEXT_PUBLIC_PASSWORD;
const auth = username && password ? 'Basic ' + btoa(username + ':' + password) : '';

export default function Home() {
  const [prompt, setPrompt] = useState('');
  const [responseMessage, setResponseMessage] = useState('');
  const [responseStatus, setResponseStatus] = useState('not sent');


  const submitPrompt = async (e: React.FormEvent) => {
    e.preventDefault(); // Prevent default form submission behavior
    console.log('Prompt sent');
    setResponseStatus('sent');
    try {
      const requestParams: any = {
        method: 'GET'
      };

      if (auth) {
        requestParams.headers = {
          'Authorization': auth,
        };
      }

      const response = await fetch(
        `${apiHost}/api/search?query=${encodeURIComponent(prompt)}`,
        requestParams
      );
      const data = await response.text();
      // const parsedData = parse(data);
      setResponseMessage(data);
      setResponseStatus('received');
      console.log('Response data:', data);
    } catch (error) {
      console.error('Error:', error);
      setResponseMessage(responseMessage);
      setResponseStatus('error');
    }
  };


  const getButtonColor = useCallback(() => {
    switch (responseStatus) {
      case 'not sent':
      case 'received':
        return 'bg-blue-500';
      case 'sent':
        return 'bg-yellow-500';
      case 'error':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  }, [responseStatus]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && responseStatus === 'sent') {
      e.preventDefault();
      return;
    }
    if (e.key === 'Enter' && !e.shiftKey && responseStatus !== 'sent') {
      e.preventDefault();
      submitPrompt(e); // Call your form submission function
    }
  }

  return (
    <div className="">
      <h2 className='hidden'>Як що заходите в перший раз, перезавантажте сторінку ще раз будь ласка, підтягнуться стилі</h2>
      <div className=' z-10 bg-[linear-gradient(340deg,#e6f4d2_1%,#a7cbe3_62%)] mb-5'>
        <form className='flex flex-row flex-wrap gap-5 max-md:gap-2 p-5 max-md:px-2  bg-[linear-gradient(340deg,#e6f4d2_1%,#a7cbe3_62%)]' onSubmit={submitPrompt}>
          <svg className='ml-5 shrink-0 ' width="50" height="50" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
            <mask id="mask0" mask-type="alpha" maskUnits="userSpaceOnUse" x="80" y="0" width="64" height="64">
              <path d="M112 64C126.022 64 133.818 64 138.909 58.9088C144 53.8177 144 46.0271 144 32C144 17.9729 144 10.1823 138.909 5.09117C133.818 0 126.022 0 112 0C97.9775 0 90.1823 0 85.0912 5.09117C80 10.1823 80 17.9775 80 32C80 46.0225 80 53.8177 85.0912 58.9088C90.1823 64 97.9775 64 112 64Z" fill="url(#paint0_linear)" />
            </mask>
            <path d="M5.80077 5.80238L5.80238 5.80077C8.13785 3.45997 11.1215 2.24496 15.3344 1.62619C19.5813 1.00245 24.9506 1 31.9942 1C39.0377 1 44.4072 1.00243 48.6558 1.6248C52.8701 2.24215 55.8571 3.45442 58.1984 5.78997C60.5399 8.13148 61.755 11.1185 62.3738 15.3329C62.9976 19.5813 63 24.9506 63 31.9942C63 39.0378 62.9976 44.4071 62.3738 48.6555C61.755 52.8699 60.5399 55.8569 58.1984 58.1984C55.8571 60.5398 52.8673 61.755 48.6512 62.3738C44.4013 62.9976 39.0319 63 31.9942 63C24.9564 63 19.5871 62.9976 15.3387 62.3738C11.1241 61.755 8.13769 60.5399 5.80238 58.1992L5.80158 58.1984C3.46022 55.8571 2.24502 52.8673 1.62621 48.6512C1.00244 44.4013 1 39.0319 1 31.9942C1 24.9564 1.00244 19.5871 1.6262 15.3387C2.24501 11.1241 3.46013 8.13769 5.80077 5.80238Z" stroke="black" strokeWidth="2" />
            <path d="M30.622 52.5657C28.3231 50.8128 26.6277 48.1979 26.0818 45.1519H18.668V13.1117C22.6622 15.0944 25.507 19.491 25.8519 24.0312L26.9726 33.0254L26.4266 32.9392C25.2197 32.9392 24.1852 34.0599 24.1852 35.1806C24.1852 36.2151 24.9898 37.1059 26.0243 37.3358L27.3749 37.6519C29.6162 33.4277 30.8806 29.2898 30.8806 25.2094C30.8806 21.5312 30.3921 17.8818 30.3346 14.1461C30.3346 12.4795 30.9668 10.9565 32.0013 9.77832C33.0358 10.9852 33.668 12.4795 33.668 14.1461C33.668 17.8818 33.122 21.5599 33.122 25.2094C33.122 29.2611 34.3864 33.4277 36.6277 37.6519L37.9783 37.3358C39.0128 37.1059 39.8174 36.2151 39.8174 35.1806C39.8174 34.0599 38.7829 32.9392 37.576 32.9392L37.03 33.0254L38.1507 24.0312C38.6967 19.491 41.3404 15.0944 45.3346 13.1117V45.1519H37.9208C37.3749 48.1691 35.7657 50.899 33.3806 52.5657C32.8346 52.968 32.3461 53.4565 32.03 54.0887C31.6565 53.4277 31.168 52.968 30.622 52.5657ZM22.1737 34.0887C22.4898 32.8818 23.3806 31.8473 24.4726 31.2151L23.5818 23.8013C23.2657 21.5025 22.3174 19.4335 20.8806 17.7381V34.0599H22.1737V34.0887ZM25.9381 42.9105C25.9381 41.7898 26.1105 40.7553 26.3404 39.7208L25.3059 39.491C23.7829 39.0025 22.6048 37.8243 22.2025 36.3013H20.9381V42.9105H25.9381ZM30.8519 42.9105C30.8519 41.5599 29.8174 40.353 28.4668 40.2094C28.2369 41.0714 28.0645 41.9622 28.0645 42.9105H30.8519ZM30.8519 45.1519H28.3806C28.7829 46.9048 29.645 48.4852 30.8519 49.8645V45.1519ZM34.3576 38.2266C33.4093 36.4737 32.5185 34.6346 31.9726 32.7381C31.4266 34.6634 30.5358 36.4737 29.5875 38.2266C30.5358 38.4565 31.3404 39.0887 31.9726 39.8071C32.6048 39.0887 33.4093 38.4565 34.3576 38.2266ZM35.8806 42.9105C35.8806 41.9622 35.7082 41.0714 35.4783 40.2094C34.1277 40.3818 33.0933 41.5599 33.0933 42.9105H35.8806ZM35.5645 45.1519H33.0933V49.8645C34.3002 48.4852 35.1622 46.9048 35.5645 45.1519ZM43.0645 42.9105V36.3013H41.8002C41.3979 37.8243 40.2197 39.0025 38.6967 39.491L37.6622 39.7208C37.8921 40.7553 38.0645 41.7898 38.0645 42.9105H43.0645ZM43.0645 34.0887V17.7668C41.6277 19.4335 40.5933 21.5025 40.3634 23.83L39.4726 31.2438C40.5933 31.876 41.4553 32.9105 41.7714 34.1174H43.0645V34.0887Z" fill="black" />
            <defs>
              <linearGradient id="paint0_linear" x1="80" y1="19.5955" x2="144" y2="19.5955" gradientUnits="userSpaceOnUse">
                <stop stopColor="#13C7FF" />
                <stop offset="1" stopColor="#FFFF36" />
              </linearGradient >
            </defs>
          </svg>
          <input disabled={responseStatus === 'sent'} className='px-5 max-h-12 mx-5 border border-gray-300 rounded-md p-2 flex-grow h-20 disabled:opacity-50 bg-white max-md:mx-0' value={prompt} placeholder='Введіть промпт... ' onChange={(e) => setPrompt(e.target.value)} onKeyDown={(e) => handleKeyDown(e)} />
          <button disabled={responseStatus === 'sent'} className={getButtonColor() + " w-40  h-12 rounded-3xl text-white  cursor-pointer disabled:cursor-default max-md:text-sm mx-auto disabled:animate-pulse"} type='submit'>
            {responseStatus === 'sent' ? 'Генерую...' : 'Згенерувати'}
          </button>
        </form> 
      </div>
      {responseMessage &&
        <div className="flex flex-row gap-10 overflow-x-scroll h-[700px] w-full px-10 isolate">
          {responseMessage
            .replaceAll('min-h-screen', 'min-h-full')
            .replaceAll('fixed', '')
            .split('\n\n\n').map(
              (screen, index) => (
                <div key={index} className="w-[360px] h-full shrink-0  bg-[#E2ECF4] mx-auto p-2 flex flex-col isolate rounded-3xl border border-gray-300">
                  <div>{parse(screen)}</div>
                </div>
              )
            )
          }
        </div>
      }
    </div>
  );
}

