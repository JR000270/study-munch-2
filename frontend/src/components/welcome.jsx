import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

export default function Welcome() {
    return (
        <section>
            <div className=" bg-amber-950">
                <p className="text-xl text-orange-500">Here is the welcome page for study munch</p>
            </div>
        </section>
    );
}