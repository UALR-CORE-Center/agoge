import {createContext, useContext} from 'react';
import type {BuildAvailability} from '../services/BuildIncidents/build-incidents.model';

export const BuildAvailabilityContext = createContext<BuildAvailability | null>(null);

export const useBuildAvailability = () => useContext(BuildAvailabilityContext);
