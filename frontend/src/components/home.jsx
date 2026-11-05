import { useOutletContext } from 'react-router-dom';
import { useState } from 'react';

export default function Home() {
    const { user } = useOutletContext();   // comes from <Outlet context={...}> in Layout
  
  
  return (
    <>
      <h2 className="text-2xl text-orange-400">Welcome back, {user.username}</h2>
      <p className="text-orange-400 text-xl pt-4 px-5" >Where should we start today?</p>
      <p className="text-orange-400 text-xl pt-4">topics</p>

      {/*box for topics list and clickable text button to add one to it*/}
      <div className="bg-amber-900 border border-amber-500 content-evenly w-300">
        <p className="text-orange-400">add new</p>
      </div>

    </>
  );
    
  
}